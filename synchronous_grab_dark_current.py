"""BSD 2-Clause License

Copyright (c) 2019, Allied Vision Technologies GmbH
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

"""
2021-06-21 13:38
Joe Created for Dark Current Calculation

"""
import sys
from typing import Optional
from vimba import *
import cv2
import numpy as np 
import time
from matplotlib import pyplot as plt 
from numpy import polyfit, poly1d




def print_preamble():
    print('//////////////////////////////////////////////////')
    print('/// Vimba API Synchronous Grab Example         ///')
    print('/// Capture Frames in different exposure time. ///')
    print('//////////////////////////////////////////////////\n')


def print_usage():
    print('Usage:')
    print('    python synchronous_grab.py [camera_id]')
    print('    python synchronous_grab.py [/h] [-h]')
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
    with Vimba.get_instance() as vimba:
        if camera_id:
            try:
                return vimba.get_camera_by_id(camera_id)

            except VimbaCameraError:
                abort('Failed to access Camera \'{}\'. Abort.'.format(camera_id))

        else:
            cams = vimba.get_all_cameras()
            if not cams:
                abort('No Cameras accessible. Abort.')

            return cams[0]


def setup_camera(cam: Camera):
    with cam:
        # Try to adjust GeV packet size. This Feature is only available for GigE - Cameras.
        try:
            cam.GVSPAdjustPacketSize.run()

            while not cam.GVSPAdjustPacketSize.is_done():
                pass
            
            

        except (AttributeError, VimbaFeatureError):
            pass


def main():
    print_preamble()
    cam_id = parse_args()
    
    # microseconds for exposure time
    expArray = [1, 10, 20, 50, 75, 100, 125, 150, 175, 200, 
                300, 350, 400, 500, 600, 700, 800, 900, 1000, 1250,
                1500, 1700, 1800, 1900, 2000, 
                2500, 3000, 3500, 4000, 4500, 
                5000, 5500, 6000, 6500, 7000, 
                7500, 8000, 8500, 9000, 9500, 9900
                ]
    a = np.array(expArray)/1000
    print(a)
    
    expSeconds = a.tolist();
    x = expSeconds[25:]          # in second
    print(x)


    #expArray =  [1,  100, 125, 400, 500, 600, 700, 1800, 1900, 2000]
                
    expAvgVal = []
    timeout = 20*1000; # 20 seconds

    i = 0
    with Vimba.get_instance():
        with get_camera(cam_id) as cam:
            setup_camera(cam)
            
            # Set MONO12
            print("The Camera support following formats: {}".format(cam.get_pixel_formats()));
            cam.set_pixel_format(PixelFormat.Mono12)
            
            # Set FPNC disabled.
            # ...
            corrName = cam.get_feature_by_name("CorrectionSelector")
            corrName.set("FixedPatternNoiseCorrection");
            corrMode = cam.get_feature_by_name("CorrectionMode")
            corrMode.set("Off");
            

            # Acquire 10 frame with a custom timeout (default is 2000ms) per frame acquisition.
            for exp in expArray:
                #for frame in cam.get_frame_generator(limit=1, timeout_ms=5000):
                #    print('Got {}'.format(frame), flush=True)
                
                # Step index
                i = i + 1
                
                feat = cam.get_feature_by_name('ExposureTime')
                feat.set(exp * 1000.000) # in us
                time.sleep(1);

                frame = cam.get_frame(timeout);

                # Save as OpenCV image
                # img = frame.as_opencv_image()
                # filename = "save" + str(i) + ".bmp"
                # cv2.imwrite(filename, img)
                
                # Save as MONO12 raw data
                img = frame.as_numpy_ndarray()
                a = np.average(img)
                expAvgVal.append(a)
            
                # print('Got {}, exporsue:{:10.3f}us, average:{:8.2f}'.format(frame, feat.get(), a), flush=True)
                print('Got Frame {:5d}, exporsue:{:10.0f}us, average:{:8.2f}'.format(i, feat.get(), a), flush=True)
                
                
    plt.plot(expArray, expAvgVal) 
    plt.show()
    
    # Only higher part of data group to be used
    startPlotIdx = 25


    y = expAvgVal[25:]
    print("x", x)
    print("y", y)
    
    coeff = polyfit(x, y, 1)
    print(coeff)
    
    f = poly1d(coeff)
    print(f)
    p = plt.plot(x, y, 'rx')
    p = plt.plot(x, f(x))


if __name__ == '__main__':
    main()
