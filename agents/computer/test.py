from time import sleep
from pynput.keyboard import Key, Controller
import pyautogui
from pynput.mouse import Button, Controller as MouseController

mouse = MouseController()
keyboard = Controller()

print("Starting in 5 seconds...")
sleep(5)
print("Pressing command+l...")
mouse.click(Button.left, 2)

print("Command+l pressed")
sleep(1)
print("Pressing command+l again...")
# pyautogui.hotkey("command", "l")
print("Command+l pressed again")