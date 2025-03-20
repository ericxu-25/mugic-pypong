# mugic-pypong
## Contents
This Python repository contains the following:
* mugic.py - module to interface with Mugic devices
* mugic_display.py - module to display the Mugic and its data
* pygame_helpers.py - simple set of custom classes and methods to make resizable pygame games
* mugical_ball.py - "Pong" example game used to demonstrate the Mugic
* quaternions/ - module with code for quaternions and simple 3d-wireframing

## Usage
\$ python mugic_display.py \[port\]

\$ python mugical_ball.py \[port1\] \[port2\]

For more options (such as recording Mugic data):
  \$ python mugic_display.py --help

Compilation as a .exe/.app can be done using the provided .spec files and setup files using [pyinstaller](https://pyinstaller.org/en/stable/) and [py2app](https://py2app.readthedocs.io/en/latest/tutorial.html) respectively.

## Credits
Created with the [pymugic](https://github.com/amiguet/pymugic/tree/main) project as a reference.

Quaternion and 3d-drawing library taken (and extended) [from peter hinch](https://github.com/peterhinch/micropython-samples/blob/master/QUATERNIONS.md)

## Attributation
Project coded by Team Mugical

Sponsored by Mari Kimura, President of MugicMotion

Created as part of:

UCI 2024-2025 Informatics Capstone Project

Professor D. Denenberg

### Team Mugical Members 
* Developer - Eric Xu
* Art & UI - Melody Chan-Yoeun
* QA Tester - Bryan Matta Villatoro
* Layout Design - Kaitlyn Ngoc Chau Train
* Theming - Shreya Padisetty
* Networks - Aj Singh
* Emotional Support - Bryan's cat
