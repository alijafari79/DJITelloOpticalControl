from djitellopy import Tello
import cv2
import pygame
from pygame.locals import *
import numpy as np
import time
import queue
import threading
from collections import deque
from plotting import Navigator
from cam_class import Camera
from timeit import default_timer as timer

# Speed of the drone
S = 60
# Frames per second of the pygame window display
FPS = 25


class FrontEnd(object):
    """ Maintains the Tello display and moves it through the keyboard keys.
        Press escape key to quit.
        The controls are:
            - T: Takeoff
            - L: Land
            - Arrow keys: Forward, backward, left and right.
            - A and D: Counter clockwise and clockwise rotations
            - W and S: Up and down.
    """

    def __init__(self):
        # Init pygame
        pygame.init()

        # Creat pygame window
        pygame.display.set_caption("Tello video stream")
        self.screen = pygame.display.set_mode([640, 480])

        # create queue and event for data communications
        self.data_queue=queue.Queue()
        self.quit_event=threading.Event()
        self.quit_event.clear()

        # Init Tello object that interacts with the Tello drone
        self.tello = Tello(self.data_queue, self.quit_event)

        # Drone velocities between -100~100
        self.for_back_velocity = 0
        self.left_right_velocity = 0
        self.up_down_velocity = 0
        self.yaw_velocity = 0
        self.speed = 10

        self.send_rc_control = False
        self.send_navigator = False
        self.face_follow = False
        self.calibrate = False

        self.cam = Camera()

        # create update timer
        pygame.time.set_timer(USEREVENT + 1, 50)


    def run(self):

        if not self.tello.connect():
            print("Tello not connected")
            return

        if not self.tello.set_speed(self.speed):
            print("Not set speed to lowest possible")
            return

        # In case streaming is on. This happens when we quit this program without the escape key.
        if not self.tello.streamoff():
            print("Could not stop video stream")
            return

        if not self.tello.streamon():
            print("Could not start video stream")
            return

        frame_read = self.tello.get_frame_read()
        self.tello.get_data_read()
        queue_diff = timer()
        directions = np.zeros(4)

        should_stop = False
        while not should_stop:
            img=cv2.resize(frame_read.frame, (640,480))

            if self.face_follow:
                img, directions = self.cam.detectFace(img)

            if self.calibrate:
                img = self.cam.calibrator(img)
                

            if not self.data_queue.empty():
                dt=timer()-queue_diff
                q=self.data_queue.get()
                # acc=q[0]*9.81
                # att=q[1]
                
                queue_diff = timer()

            for event in pygame.event.get():
                if event.type == USEREVENT + 1:
                    self.update(directions)
                elif event.type == QUIT:
                    should_stop = True
                    self.quit_event.set()
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        should_stop = True
                        self.quit_event.set()
                    else:
                        self.keydown(event.key)
                elif event.type == KEYUP:
                    self.keyup(event.key)

            if frame_read.stopped:
                frame_read.stop()
                break

            # cv2.imshow("frame",img)
            # print("showing")

            # c=cv2.waitKey(1)

            # if c==27:
            #     should_stop = True
            #     break
            # elif c==116:
            #     self.tello.takeoff()
            #     self.send_rc_control = True
            # elif c==108:
            #     self.tello.land()
            #     self.send_rc_control = False
            
            self.screen.fill([0, 0, 0])
            frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            frame = np.rot90(frame)
            frame = np.flipud(frame)
            frame = pygame.surfarray.make_surface(frame)
            self.screen.blit(frame, (0, 0))
            pygame.display.update()

            time.sleep(1 / FPS)

        # Call it always before finishing. I deallocate resources.
        self.tello.end()

    def keydown(self, key):
        """ Update velocities based on key pressed
        Arguments:
            key: pygame key
        """
        if key == pygame.K_UP:  # set forward velocity
            self.for_back_velocity = S
        elif key == pygame.K_DOWN:  # set backward velocity
            self.for_back_velocity = -S
        elif key == pygame.K_LEFT:  # set left velocity
            self.left_right_velocity = -S
        elif key == pygame.K_RIGHT:  # set right velocity
            self.left_right_velocity = S
        elif key == pygame.K_w:  # set up velocity
            self.up_down_velocity = S
        elif key == pygame.K_s:  # set down velocity
            self.up_down_velocity = -S
        elif key == pygame.K_a:  # set yaw clockwise velocity
            self.yaw_velocity = -S
        elif key == pygame.K_d:  # set yaw counter clockwise velocity
            self.yaw_velocity = S

    def keyup(self, key):
        """ Update velocities based on key released
        Arguments:
            key: pygame key
        """
        if key == pygame.K_UP or key == pygame.K_DOWN:  # set zero forward/backward velocity
            self.for_back_velocity = 0
        elif key == pygame.K_LEFT or key == pygame.K_RIGHT:  # set zero left/right velocity
            self.left_right_velocity = 0
        elif key == pygame.K_w or key == pygame.K_s:  # set zero up/down velocity
            self.up_down_velocity = 0
        elif key == pygame.K_a or key == pygame.K_d:  # set zero yaw velocity
            self.yaw_velocity = 0
        elif key == pygame.K_t:  # takeoff
            self.tello.takeoff()
            self.send_rc_control = True
        elif key == pygame.K_l:  # land
            self.tello.land()
            self.send_rc_control = False
        # elif key == pygame.K_n:
        #     self.send_navigator = True
        # elif key == pygame.K_m:
        #     self.send_navigator = False
        # elif key == pygame.K_f:
        #     self.face_follow = True
        # elif key == pygame.K_g:
        #     self.face_follow = False
        elif key == pygame.K_k:
            self.calibrate = True
        elif key == pygame.K_l:
            self.calibrate = False

    def update(self, dirs):
        """ Update routine. Send velocities to Tello."""
        if self.send_rc_control:
            if self.send_navigator:
                navi=Navigator()
                vx,vy,vz=navi.velos()
                for i in range(len(vx)):
                    self.tello.send_rc_control(int(20*vx[i]), int(20*vy[i]), int(200*vz[i]), 0)
                    time.sleep(0.5)
                self.send_navigator=False
            elif self.face_follow:
                dirs=dirs*20
                self.tello.send_rc_control(int(dirs[0]), int(dirs[1]), int(dirs[2]), int(dirs[3]*2))
            else:
                self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity,
                                           self.yaw_velocity)
            
        


def main():
    frontend = FrontEnd()

    # run frontend
    frontend.run()


if __name__ == '__main__':
    main()
