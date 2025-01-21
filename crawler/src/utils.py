import sys

def bring_window_to_front(driver):
    if sys.platform == 'win32':
        position = driver.get_window_position
        driver.minimize_window()
        driver.set_window_position(position['x'], position['y'])
    else:
        driver.fullscreen_window()
        driver.set_window_size(1024, 600)