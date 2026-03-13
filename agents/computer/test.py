from time import sleep
from pynput.keyboard import Key, Controller


keyboard = Controller()

print("Starting in 5 seconds...")
sleep(5)
print("Pressing command+l...")
keyboard.press(Key.cmd)
keyboard.press('l')
keyboard.release('l')
keyboard.release(Key.cmd)
print("Command+l pressed")
sleep(1)
print("Pressing command+l again...")
# pyautogui.hotkey("command", "l")
print("Command+l pressed again")