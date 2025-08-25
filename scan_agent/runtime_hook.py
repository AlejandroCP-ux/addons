import sys
import os

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
    scan_dir = os.path.join(base_dir, 'scan')
    if os.path.exists(scan_dir):
        sys.path.insert(0, scan_dir)
        sys.path.insert(0, os.path.join(scan_dir, 'core'))
        sys.path.insert(0, os.path.join(scan_dir, 'hardware'))
        sys.path.insert(0, os.path.join(scan_dir, 'sistema'))