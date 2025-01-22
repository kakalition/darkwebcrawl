import logging
import sys


def bring_window_to_front(driver):
    logging.info('bring to front')
    if sys.platform == 'win32':
        logging.info('win32')
        driver.minimize_window()
        driver.set_window_position(0, 0)
    else:
        logging.info('mac')
        driver.fullscreen_window()
        driver.set_window_size(1024, 600)