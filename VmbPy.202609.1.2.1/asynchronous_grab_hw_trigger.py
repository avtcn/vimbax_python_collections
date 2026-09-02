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
from typing import Optional, Tuple

from vmbpy import *


def print_preamble():
    print('/////////////////////////////////////////////')
    print('/// VmbPy Asynchronous Grab Example ///')
    print('/// VmbPy 1.2.1 Hardware Trigger ///')
    print('/// Line0/Line1 works ///')
    print('/////////////////////////////////////////////\n')


def print_usage():
    print('Usage:')
    print('    python asynchronous_grab.py [/x] [-x] [camera_id]')
    print('    python asynchronous_grab.py [/h] [-h]')
    print()
    print('Parameters:')
    print('    /x, -x      If set, use AllocAndAnnounce mode of buffer allocation')
    print('    camera_id   ID of the camera to use (using first camera if not specified)')
    print()


def abort(reason: str, return_code: int = 1, usage: bool = False):
    print(reason + '\n')

    if usage:
        print_usage()

    sys.exit(return_code)


def parse_args() -> Tuple[Optional[str], AllocationMode]:
    args = sys.argv[1:]
    argc = len(args)

    allocation_mode = AllocationMode.AnnounceFrame
    cam_id = ""
    for arg in args:
        if arg in ('/h', '-h'):
            print_usage()
            sys.exit(0)
        elif arg in ('/x', '-x'):
            allocation_mode = AllocationMode.AllocAndAnnounceFrame
        elif not cam_id:
            cam_id = arg

    if argc > 2:
        abort(reason="Invalid number of arguments. Abort.", return_code=2, usage=True)

    return (cam_id if cam_id else None, allocation_mode)


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

        # Configure hardware trigger as trigger source.
        # There are 4 trigger lines total; set the line to the desired one below:
        #   Line0 -> 1st trigger line  (LineSelector='Line0', TriggerSource='Line0')
        #   Line1 -> 2nd trigger line  (LineSelector='Line1', TriggerSource='Line1')
        #   Line2 -> 3rd trigger line  (LineSelector='Line2', TriggerSource='Line2')
        #   Line3 -> 4th trigger line  (LineSelector='Line3', TriggerSource='Line3')
        # Feature names may vary between camera models, so each step is guarded.
        cam.TriggerSelector.set('FrameStart')
        cam.TriggerMode.set('Off')

        # Configure Line1 as input and source.
        cam.LineSelector.set('Line1')
        if 'Input' in cam.LineMode.get_available_entries():
            cam.LineMode.set('Input')
        try:
            cam.LineSource.set('Line1')
        except (AttributeError, VmbFeatureError):
            pass

        # Set Line1 as the trigger source (and optional activation edge).
        cam.TriggerSource.set('Line1')
        try:
            cam.TriggerActivation.set('RisingEdge')
        except (AttributeError, VmbFeatureError):
            pass

        # Enable hardware trigger.
        cam.TriggerMode.set('On')

        trigger_source = str(cam.TriggerSource.get())
        line_index = trigger_source.replace('Line', '')
        ordinals = {'0': '1st', '1': '2nd', '2': '3rd', '3': '4th'}
        line_desc = '{} trigger line, all 4 lines'.format(ordinals.get(line_index, line_index)) \
            if line_index in ordinals else trigger_source

        print('Trigger configured: source={} (the {}), selector={}, activation={}, mode={}'.format(
            trigger_source,
            line_desc,
            cam.TriggerSelector.get(),
            cam.TriggerActivation.get(),
            cam.TriggerMode.get()), flush=True)


def frame_handler(cam: Camera, stream: Stream, frame: Frame):
    print('{} acquired {}'.format(cam, frame), flush=True)

    cam.queue_frame(frame)


def main():
    print_preamble()
    cam_id, allocation_mode = parse_args()

    with VmbSystem.get_instance():
        with get_camera(cam_id) as cam:

            setup_camera(cam)
            print('Press <enter> to stop Frame acquisition.')

            try:
                # Start Streaming with a custom a buffer of 10 Frames (defaults to 5)
                cam.start_streaming(handler=frame_handler,
                                    buffer_count=10,
                                    allocation_mode=allocation_mode)
                input()

            finally:
                cam.stop_streaming()


if __name__ == '__main__':
    main()
