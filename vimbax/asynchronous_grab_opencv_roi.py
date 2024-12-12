"""BSD 2-Clause License

Copyright (c) 2023, Allied Vision Technologies GmbH
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
from typing import Optional
from queue import Queue

import numpy as np


from vmbpy import *


# All frames will either be recorded in this format, or transformed to it before being displayed
opencv_display_format = PixelFormat.Bgr8


def print_preamble():
    print('///////////////////////////////////////////////////')
    print('/// VmbPy Asynchronous Grab with OpenCV Example ///')
    print('/// - ROI                                       ///')
    print('/// - Pixels Values Sum                         ///')
    print('///                                             ///')
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

        # Disable auto exposure time setting if camera supports it
        try:
            cam.ExposureAuto.set('Off')
        except (AttributeError, VmbFeatureError):
            print("ERROR1:", VmbFeatureError)
            pass

        # Set ExposureTime, ROI, etc,.
        try:
            # feature_exp = cam.get_feature_by_name('ExposureTime')
            feature_exp = cam.get_feature_by_name('ExposureTime')
            exp_old = feature_exp.get()
            print("origin exposure time:", exp_old)
            feature_exp.set(640) # 12.345ms
            exp_new = feature_exp.get()
            print("new exposure time:", exp_new)


            width = cam.get_feature_by_name('Width')
            height = cam.get_feature_by_name('Height')
            width.set(64)
            height.set(64)
            print("new width:", width.get(), "new height:", height.get())

            offsetx = cam.get_feature_by_name('OffsetX')
            offsety = cam.get_feature_by_name('OffsetY')
            offsetx.set(600)
            offsety.set(500)
            print("new offsetx:", offsetx.get(), "new offsety:", offsety.get())

            # set fps for Stingray F125
            fps = cam.get_feature_by_name('AcquisitionFrameRate')
            fps.set(11.0) 



        except (AttributeError, VmbFeatureError):
            print("ERROR2:", VmbFeatureError)
            pass

        # Enable white balancing if camera supports it
        # try:
        #     cam.BalanceWhiteAuto.set('Continuous')
        # except (AttributeError, VmbFeatureError):
        #     pass

        # Try to adjust GeV packet size. This Feature is only available for GigE - Cameras.
        try:
            stream = cam.get_streams()[0]
            stream.GVSPAdjustPacketSize.run()
            while not stream.GVSPAdjustPacketSize.is_done():
                pass

        except (AttributeError, VmbFeatureError):
            # print("ERROR3:", VmbFeatureError)
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
        print("set pixel format #1:", opencv_display_format)

    # else if existing color format can be converted to OpenCV format do that
    elif convertible_color_formats:
        cam.set_pixel_format(convertible_color_formats[0])
        print("set pixel format #2:", convertible_color_formats[0])

    # fall back to a mono format that can be converted
    elif convertible_mono_formats:
        # cam.set_pixel_format(convertible_mono_formats[0])
        cam.set_pixel_format(convertible_mono_formats[2])
        print("set pixel format #3:", convertible_mono_formats[0])
        print("set pixel format #3:", convertible_mono_formats[1])
        print("set pixel format #3:", convertible_mono_formats[2])
        print("set pixel format #3:", convertible_mono_formats)
        print("set pixel format #3: current value:", cam.get_pixel_format())

    else:
        abort('Camera does not support an OpenCV compatible format. Abort.')


class Handler:
    def __init__(self):
        self.display_queue = Queue(10)

    def get_image(self):
        return self.display_queue.get(True)

    def __call__(self, cam: Camera, stream: Stream, frame: Frame):
        if frame.get_status() == FrameStatus.Complete:
            print('{} acquired {}'.format(cam, frame), flush=True)

            # Convert frame if it is not already the correct format
            # if frame.get_pixel_format() == opencv_display_format:
            #     display = frame
            # else:
            #     # This creates a copy of the frame. The original `frame` object can be requeued
            #     # safely while `display` is used
            #     display = frame.convert_pixel_format(opencv_display_format)

            # keep original vimbax frame 
            display = frame
            
            # self.display_queue.put(display.as_opencv_image(), True)
            self.display_queue.put(display, True)

        cam.queue_frame(frame)


def main():
    print_preamble()
    cam_id = parse_args()

    # Specify the file name
    file_name = "output.txt"

    # Open the file in write mode
    file = open(file_name, "w")

    with VmbSystem.get_instance():
        with get_camera(cam_id) as cam:
            # setup general camera settings and the pixel format in which frames are recorded
            setup_camera(cam)
            setup_pixel_format(cam)
            handler = Handler()

            try:
                # Start Streaming with a custom a buffer of 10 Frames (defaults to 5)
                cam.start_streaming(handler=handler, buffer_count=10)

                msg = 'Stream from \'{}\'. Press <Enter> to stop stream.'
                import cv2
                ENTER_KEY_CODE = 13
                while True:
                    key = cv2.waitKey(1)
                    if key == ENTER_KEY_CODE:
                        cv2.destroyWindow(msg.format(cam.get_name()))
                        break

                    frame = handler.get_image()

                    if frame.get_pixel_format() == opencv_display_format:
                        display = frame
                    else:
                        # This creates a copy of the frame. The original `frame` object can be requeued
                        # safely while `display` is used
                        display = frame.convert_pixel_format(opencv_display_format)

                    img_opencv = frame.as_opencv_image()
                    img_numpy = frame.as_numpy_ndarray()

                    print("image   as array:", img_numpy.shape, img_numpy.dtype)

                    mean_value = np.mean(img_numpy)
                    total_sum = np.sum(img_numpy)
                    print("image frame info:", frame.get_buffer_size(), ", mean:",  mean_value ,", sum:", total_sum)
                    # print(img_numpy)

                    # Write the text to the file
                    file.write(f"{mean_value},{total_sum}\n")



                    cv2.imshow(msg.format(cam.get_name()), img_opencv)

            finally:
                file.close()
                cam.stop_streaming()


if __name__ == '__main__':
    main()
