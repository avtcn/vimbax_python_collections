"""BSD 2-Clause License

Copyright (c) 2022, Allied Vision Technologies GmbH
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import sys
import threading
from typing import Optional

import cv2

import numpy as np

import tifffile
import imageio.v3 as iio



from vmbpy import *

# All frames will either be recorded in this format, or transformed to it before being displayed
opencv_display_format = PixelFormat.Bgr8
opencv_display_format = PixelFormat.Bgr8


def print_preamble():
    print('///////////////////////////////////////////////////')
    print('/// VmbPy Asynchronous Grab with OpenCV Example ///')
    print('/// BayerRG12 to 12bit TIFF image               ///')
    print('///////////////////////////////////////////////////\n')


def print_usage():
    print('Usage:')
    print('    python asynchronous_grab_opencv.py [camera_id]')
    print('    python asynchronous_grab_opencv.py [/h] [-h]')
    print()
    print('Parameters:')
    print('    camera_id   ID of the camera to use (using first camera if not specified)')
    print()


def abort(reason: str, return_code: int = 1, usage: bool = False):
    print(reason + '\n')

    if usage:
        print_usage()

    sys.exit(return_code)


def parse_args() -> Optional[str]:
    args = sys.argv[1:]
    argc = len(args)

    for arg in args:
        if arg in ('/h', '-h'):
            print_usage()
            sys.exit(0)

    if argc > 1:
        abort(reason="Invalid number of arguments. Abort.", return_code=2, usage=True)

    return None if argc == 0 else args[0]


def get_camera(camera_id: Optional[str]) -> Camera:
    with VmbSystem.get_instance() as vmb:
        if camera_id:
            try:
                return vmb.get_camera_by_id(camera_id)

            except VmbCameraError:
                abort('Failed to access Camera \'{}\'. Abort.'.format(camera_id))

        else:
            cams = vmb.get_all_cameras()
            if not cams:
                abort('No Cameras accessible. Abort.')

            return cams[0]


def setup_camera(cam: Camera):
    with cam:

        # Try to adjust GeV packet size. This Feature is only available for GigE - Cameras.
        try:
            stream = cam.get_streams()[0]
            stream.GVSPAdjustPacketSize.run()
            while not stream.GVSPAdjustPacketSize.is_done():
                pass

        except (AttributeError, VmbFeatureError):
            pass


def setup_pixel_format(cam: Camera):
    # Query available pixel formats. Prefer color formats over monochrome formats
    cam_formats = cam.get_pixel_formats()
    cam_color_formats = intersect_pixel_formats(cam_formats, COLOR_PIXEL_FORMATS)
    convertible_color_formats = tuple(f for f in cam_color_formats
                                      if opencv_display_format in f.get_convertible_formats())

    cam_mono_formats = intersect_pixel_formats(cam_formats, MONO_PIXEL_FORMATS)
    convertible_mono_formats = tuple(f for f in cam_mono_formats
                                     if opencv_display_format in f.get_convertible_formats())

    # if OpenCV compatible color format is supported directly, use that
    if opencv_display_format in cam_formats:
        cam.set_pixel_format(opencv_display_format)

    # else if existing color format can be converted to OpenCV format do that
    elif convertible_color_formats:
        cam.set_pixel_format(convertible_color_formats[0])

    # fall back to a mono format that can be converted
    elif convertible_mono_formats:
        cam.set_pixel_format(convertible_mono_formats[0])

    else:
        abort('Camera does not support an OpenCV compatible format. Abort.')


class Handler:
    def __init__(self):
        self.shutdown_event = threading.Event()

    def __call__(self, cam: Camera, stream: Stream, frame: Frame):
        ENTER_KEY_CODE = 13

        key = cv2.waitKey(1)
        if key == ENTER_KEY_CODE:
            self.shutdown_event.set()
            return

        elif frame.get_status() == FrameStatus.Complete:
            print('{} acquired {} in {}'.format(cam, frame, frame.get_pixel_format()), flush=True)
            # Convert frame if it is not already the correct format
            if frame.get_pixel_format() == opencv_display_format:
                display = frame
            else:
                # This creates a copy of the frame. The original `frame` object can be requeued
                # safely while `display` is used
                # display in opencv_display_format = PixelFormat.Bgr8 to show 
                display = frame.convert_pixel_format(opencv_display_format)

                # BayerRG12 to 12 bit TIFF
                height = frame.get_height()
                width = frame.get_width()
                #bayer_raw_data = frame.get_buffer()
                bayer_raw_data = np.frombuffer(frame.get_buffer(), dtype=np.uint16)

                # 检查数据大小是否匹配, BayerRG12, use 16 bit to contain 12 bit pixel value
                if frame.get_buffer_size() != width * height * 2:
                    raise ValueError(f"原始数据大小与指定的宽度和高度不匹配。期望 {width * height * 2}，实际 {frame.get_buffer_size()}")

                # 16 bit raw data array's size is matched with W * H
                if bayer_raw_data.size != width * height:
                    raise ValueError(f"原始数据大小与指定的宽度和高度不匹配。期望 {width * height}，实际 {bayer_raw_data.size}")
                
                # 将一维数据 reshape 成二维图像
                bayer_image_16bit = bayer_raw_data.reshape((height, width))
                pixel_value1 = bayer_image_16bit[0, 0]
                pixel_value2 = bayer_image_16bit[100, 100]
                pixel_value3 = bayer_image_16bit[200, 200]
                print('BayerRG12 raw data origin: {}, {}, {}'.format(pixel_value1, pixel_value2, pixel_value3), flush=True)

                # 由于是 BayerRG12，可能高 12 位有效，需右移 4 位转换为 8/12bit 可视图
                # 如果你想保存 16bit RGB，可以保留原精度
                bayer_image_16bit = (bayer_image_16bit << 4).astype(np.uint16)  # 或保持 np.uint16 看需求
                pixel_value1 = bayer_image_16bit[0, 0]
                pixel_value2 = bayer_image_16bit[100, 100]
                pixel_value3 = bayer_image_16bit[200, 200]
                print('BayerRG12 raw data tiff  : {}, {}, {}'.format(pixel_value1, pixel_value2, pixel_value3), flush=True)

                # 3. 去马赛克 (Demosaicing)
                # 对于BayerRG12，对应的OpenCV去马赛克模式是 COLOR_BayerBG2RGB
                # 这是因为OpenCV中的Bayer模式命名与实际的拜耳模式可能存在差异。
                # BayerRG 通常对应 OpenCV 的 COLOR_BayerGR2RGB。
                # 但对于工业相机，BayerRG12的"RG"通常指的是第一行第一个像素是R，
                # 第二个是G，然后第二行第一个是G，第二个是B。
                # 实际使用中，你需要根据你的相机文档或实际测试来确定正确的Bayer模式。
                rgb_image = cv2.cvtColor(bayer_image_16bit, cv2.COLOR_BAYER_RG2RGB_EA )

                #TODO: saved tiff seems very black, Use Ctrl+I inverse and see something ...

                output_tiff_path = "output_" + str(frame.get_id()) + ".tiff"

                # 直接保存16位RGB图像为TIFF, compressed
                cv2.imwrite(output_tiff_path, rgb_image) 

                # Save as TIFF without compression
                #tifffile.imwrite(output_tiff_path, rgb_image, compression=None)
                # Save as 16-bit TIFF with no compression
                #iio.imwrite(output_tiff_path, rgb_image, extension=".tiff", compression="none")

                print(f"成功将BayerRG12数据转换为RGB TIFF并保存到: {output_tiff_path}")





            msg = 'Stream from \'{}\' in format {}. Press <Enter> to stop stream.'
            cv2.imshow(msg.format(cam.get_name(), frame.get_pixel_format()), display.as_opencv_image())

        cam.queue_frame(frame)


def main():
    print_preamble()
    cam_id = parse_args()

    with VmbSystem.get_instance():
        with get_camera(cam_id) as cam:
            # setup general camera settings and the pixel format in which frames are recorded
            setup_camera(cam)
            # Keep camera's origin BayerRG12 format
            #setup_pixel_format(cam)
            handler = Handler()

            try:
                # Start Streaming with a custom a buffer of 10 Frames (defaults to 5)
                cam.start_streaming(handler=handler, buffer_count=10)
                handler.shutdown_event.wait()

            finally:
                cam.stop_streaming()


if __name__ == '__main__':
    main()
