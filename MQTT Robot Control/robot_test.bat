@echo off
REM Pretend to be the professor: publish Homework 9 commands to your own Mosquitto broker.
REM Double-click this file, then press keys. Change BROKER if the broker runs on another computer.
setlocal
set BROKER=localhost
set PUB="C:\Program Files\mosquitto\mosquitto_pub.exe" -h %BROKER% -p 1883

:menu
echo.
echo  DIRECTION:  w=forward  s=backward  a=left  d=right  x=stop
echo  SPEED:      1=20  2=50  3=100  0=0  p=type a speed
echo  LEDS:       r=red  g=green  b=blue  m=magenta  o=off
echo  q=quit
choice /c wsadx1230prgbmoq /n /m "Command: "
goto c%errorlevel%

:c1
%PUB% -t ME35/direction -m forward & goto menu
:c2
%PUB% -t ME35/direction -m backward & goto menu
:c3
%PUB% -t ME35/direction -m left & goto menu
:c4
%PUB% -t ME35/direction -m right & goto menu
:c5
%PUB% -t ME35/direction -m stop & goto menu
:c6
%PUB% -t ME35/speed -m 20 & goto menu
:c7
%PUB% -t ME35/speed -m 50 & goto menu
:c8
%PUB% -t ME35/speed -m 100 & goto menu
:c9
%PUB% -t ME35/speed -m 0 & goto menu
:c10
set /p SPD="Speed (0-100): "
%PUB% -t ME35/speed -m %SPD% & goto menu
:c11
call :leds 255 0 0 & goto menu
:c12
call :leds 0 255 0 & goto menu
:c13
call :leds 0 0 255 & goto menu
:c14
call :leds 255 0 122 & goto menu
:c15
call :leds 0 0 0 & goto menu
:c16
exit /b

:leds
%PUB% -t ME35/led/0 -m "{\"r\": %1, \"g\": %2, \"b\": %3}"
%PUB% -t ME35/led/1 -m "{\"r\": %1, \"g\": %2, \"b\": %3}"
exit /b
