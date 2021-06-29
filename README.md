# vmb_python_collections
Vimba Python API test examples collections.

## Tools
* Spyder
* PyCharm

## Testing Sampels
1. multithreading_opencv_missing_frames.py   
  Multiple cameras in asynchronous capturing mode.
  
2. synchronous_grab_dark_current.py  
  Capture multiple photos in different exposure time.
  
  
  
## Linux USB
``` 
sudo sh -c 'echo 2048 > /sys/module/usbcore/parameters/usbfs_memory_mb'
```