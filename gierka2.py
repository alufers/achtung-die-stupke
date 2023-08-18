"""Control a game with your feet."""

import base64
import inspect
import json
import math
import os
import pathlib

# import matplotlib
import queue
import re
import sys
import threading
import uuid
from io import BytesIO

import AVFoundation
import cv2
import numpy as np
import Quartz
import tornado
import Vision
from Cocoa import NSURL
from Foundation import NSDictionary
from PIL import Image, ImageDraw, ImageFont
from tornado.websocket import WebSocketHandler

# needed to capture system-level stderr
from wurlitzer import pipes

clients = []

evt_queue_lock = threading.Lock()
evt_queue = queue.Queue()


class WebSocketHandler(WebSocketHandler):
    def open(self):
        print("WebSocket opened")
        clients.append(self)
        self.write_message("{}")

    def on_message(self, message):
        print("Message received: {}".format(message))
        parsed = json.loads(message)
        with evt_queue_lock:
            evt_queue.put(parsed)

    def on_close(self):
        print("WebSocket closed")
        clients.remove(self)

    def check_origin(self, origin):
        return True


def start_tornado():
    app = tornado.web.Application(
        [
            (r"/websocket", WebSocketHandler),
            (r"/(.*)", tornado.web.StaticFileHandler, {"path": "./static"}),
        ]
    )

    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()


calibration_config = {
    "min_bb_height": 0,
    "min_bb_width": 0,
    "left_deadzone": 0,
    "right_deadzone": 0,
}


def save_calibration():
    global calibration_config
    serialized_calib = json.dumps(calibration_config)
    with open("calibration.json", "w") as f:
        f.write(serialized_calib)


def load_calibration():
    global calibration_config
    try:
        with open("calibration.json", "r") as f:
            calibration_config = json.loads(f.read())
    except:
        pass


# Start Tornado server in a separate thread
tornado_thread = threading.Thread(target=start_tornado)
tornado_thread.start()


last_sent = None


def send_json(data):
    
    global last_sent
    dumped = json.dumps(data)
    if dumped == last_sent:
        return
    last_sent = dumped
    for client in clients:
        client.write_message(dumped)


img = None
draw = None

font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 20)
font_big = ImageFont.truetype("/Library/Fonts/Arial.ttf", 40)


TRACK_N_FRAMES = 40
# TRACKED_OBSERVATION_MAX_TIME_SINCE_LAST_MATCH = 30
MATCH_MAX_BB_X_DIST = 180
MATCH_MAX_BB_Y_DIST = 180
MATCH_MAX_BB_HEIGHT_DIST = 140


class ObservationState:
    def __init__(
        self,
        bb_center_x=None,
        bb_center_y=None,
        bb_height=None,
        foot_diff=None,
    ):
        self.bb_center_x = bb_center_x
        self.bb_center_y = bb_center_y
        self.bb_height = bb_height
        self.foot_diff = foot_diff

    def matches(self, other):
        if abs(self.bb_center_x - other.bb_center_x) > MATCH_MAX_BB_X_DIST:
            return False
        if abs(self.bb_center_y - other.bb_center_y) > MATCH_MAX_BB_Y_DIST:
            return False
        if abs(self.bb_height - other.bb_height) > MATCH_MAX_BB_HEIGHT_DIST:
            return False
        return True

    def distance(self, other):
        return math.sqrt(
            (self.bb_center_x - other.bb_center_x) ** 2
            + (self.bb_center_y - other.bb_center_y) ** 2
        )


class TrackedObservation:
    def __init__(self):
        self.age = 0
        self.time_since_last_match = 0
        self.last_states = []
        self.foot_image_data = None
        self.uuid = str(uuid.uuid4())

    def push_state(self, state):
        self.last_states.append(state)
        self.last_states = self.last_states[-TRACK_N_FRAMES:]
        self.time_since_last_match = 0

    def last_state(self):
        return self.last_states[-1]

    def last_foot_diff(self):
        for i in range(len(self.last_states) - 1, 0, -1):
            state = self.last_states[i]
            if state.foot_diff is not None:
                return state.foot_diff
        return None

    def last_bb_center_x(self):
        for i in range(len(self.last_states) - 1, 0, -1):
            state = self.last_states[i]
            if state.bb_center_x is not None:
                return state.bb_center_x
        return None

    def last_height(self):
        for i in range(len(self.last_states) - 1, 0, -1):
            state = self.last_states[i]
            if state.bb_height is not None:
                return state.bb_height
        return None

    def draw_history(self):
        # walk last states backwards
        for i in range(len(self.last_states) - 1, 0, -1):
            state = self.last_states[i]
            prev_state = self.last_states[i - 1]
            draw.line(
                (
                    state.bb_center_x,
                    state.bb_center_y,
                    prev_state.bb_center_x,
                    prev_state.bb_center_y,
                ),
                fill=(0, 0, 255, 255),
                width=3,
            )
            draw.ellipse(
                (
                    state.bb_center_x - 10,
                    state.bb_center_y - 10,
                    state.bb_center_x + 10,
                    state.bb_center_y + 10,
                ),
                fill=(0, 0, 255, 255),
            )


tracked_observations = []


# img = Image.open(sys.argv[1])
# draw = ImageDraw.Draw(img)
def detect_points(img_path, lang="eng"):
    input_url = NSURL.fileURLWithPath_(img_path)

    with pipes() as (out, err):
        # capture stdout and stderr from system calls
        # otherwise, Quartz.CIImage.imageWithContentsOfURL_
        # prints to stderr something like:
        # 2020-09-20 20:55:25.538 python[73042:5650492] Creating client/daemon connection: B8FE995E-3F27-47F4-9FA8-559C615FD774
        # 2020-09-20 20:55:25.652 python[73042:5650492] Got the query meta data reply for: com.apple.MobileAsset.RawCamera.Camera, response: 0
        input_image = Quartz.CIImage.imageWithContentsOfURL_(input_url)

    vision_options = NSDictionary.dictionaryWithDictionary_({})
    vision_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
        input_image, vision_options
    )
    results = []
    handler = make_request_handler(results)
    vision_request = (
        Vision.VNDetectHumanBodyPoseRequest.alloc().initWithCompletionHandler_(handler)
    )
    error = vision_handler.performRequests_error_([vision_request], None)

    return results


def make_request_handler(results):
    """results: list to store results"""
    if not isinstance(results, list):
        raise ValueError("results must be a list")

    def handler(request, error):
        if error:
            print(f"Error! {error}")
        else:
            observations = request.results()
            observations_data = []
            for obs in observations:
                joints = []
                confidence = obs.confidence()
                # round to 2 decimal places
                confidence = round(confidence, 2)
                bb_min_x = 99999
                bb_min_y = 99999
                bb_max_x = 0
                bb_max_y = 0

                left_foot_y = None
                left_foot_x = None
                right_foot_y = None
                right_foot_x = None

                left_knee_y = None
                left_knee_x = None

                for join_name in obs.availableJointNames():
                    pkt = obs.recognizedPointForJointName_error_(join_name, None)
                    str_of_pkt = str(pkt)
                    matches = re.findall(r"\d+\.\d+", str_of_pkt)

                    (x, y) = (float(matches[0]), float(matches[1]))

                    if not (
                        abs(x) > 0.01
                        and abs(y) > 0.01
                        and abs(x) < 0.99
                        and abs(y) < 0.99
                    ):
                        continue
                    # x = 1 - x
                    y = 1 - y
                    # draw point on image
                    img_x = x * img.size[0]
                    img_y = y * img.size[1]
                    if img_x < bb_min_x:
                        bb_min_x = img_x
                    if img_y < bb_min_y:
                        bb_min_y = img_y
                    if img_x > bb_max_x:
                        bb_max_x = img_x
                    if img_y > bb_max_y:
                        bb_max_y = img_y
                    # draw.ellipse((img_x-10, img_y-10, img_x+10, img_y+10), fill=(255,0,0,255))
                    # draw joint name
                    # draw.text((img_x + 15, img_y), join_name + " " + str(confidence), fill=(255,0,0,255), font=font)

                    joints.append(
                        {
                            "name": join_name,
                            "x": img_x,
                            "y": img_y,
                        }
                    )
                    if join_name == "right_foot_joint":
                        right_foot_x = img_x
                        right_foot_y = img_y
                    if join_name == "left_foot_joint":
                        left_foot_x = img_x
                        left_foot_y = img_y
                    if join_name == "left_leg_joint":
                        left_knee_x = img_x
                        left_knee_y = img_y

                is_bb_big_valid = (
                    bb_max_y - bb_min_y >= calibration_config["min_bb_height"]
                )
                if bb_max_x - bb_min_x < calibration_config["min_bb_width"]:
                    is_bb_big_valid = False
                bb_center_x = (bb_max_x + bb_min_x) / 2
                bb_center_y = (bb_max_y + bb_min_y) / 2
                # check if center is in deadzone
                if (
                    bb_center_x >= 0
                    and bb_center_x <= calibration_config["left_deadzone"]
                ):
                    is_bb_big_valid = False
                if (
                    bb_center_x >= img.size[0] - calibration_config["right_deadzone"]
                    and bb_center_x <= img.size[0]
                ):
                    is_bb_big_valid = False

                draw.rectangle(
                    (bb_min_x, bb_min_y, bb_max_x, bb_max_y),
                    outline=(255, 0, 0, 255) if is_bb_big_valid else (0, 0, 0, 255),
                    width=3,
                )
                if not is_bb_big_valid:
                    continue
                foot_diff = None
                if left_foot_x and left_foot_y and right_foot_x and right_foot_y:
                    left_foot_vert_perc = (left_foot_y - bb_min_y) / (
                        bb_max_y - bb_min_y
                    )
                    right_foot_vert_perc = (right_foot_y - bb_min_y) / (
                        bb_max_y - bb_min_y
                    )
                    foot_diff = left_foot_vert_perc - right_foot_vert_perc
                    # draw on img
                    # draw.text((bb_min_x, bb_min_y + 5), "L: " + str(round(left_foot_vert_perc, 2)) + " R: " + str(round(right_foot_vert_perc, 2)) , fill=(255,0,0,255), font=font)
                    draw.text(
                        (bb_min_x, bb_min_y + 5),
                        "D: " + str(round(foot_diff, 2)),
                        fill=(255, 0, 255, 255),
                        font=font_big,
                    )
                observations_data.append(
                    {
                        "joints": joints,
                        "confidence": confidence,
                        "bb_min_x": bb_min_x,
                        "bb_min_y": bb_min_y,
                        "bb_max_x": bb_max_x,
                        "bb_max_y": bb_max_y,
                        "foot_diff": foot_diff,
                    }
                )

                # track observations
                curr_state = ObservationState(
                    bb_center_x=bb_center_x,
                    bb_center_y=bb_center_y,
                    bb_height=bb_max_y - bb_min_y,
                    foot_diff=foot_diff,
                )
                match_candidates = [
                    obs
                    for obs in tracked_observations
                    if curr_state.matches(obs.last_state())
                ]

                current_tracked_observation = None
                if len(match_candidates) == 0:
                    if foot_diff is not None:
                        tracked_observations.append(TrackedObservation())
                        current_tracked_observation = tracked_observations[-1]
                        current_tracked_observation.push_state(curr_state)
                        # draw a filled rectangle
                        draw.rectangle(
                            (bb_min_x, bb_min_y, bb_max_x, bb_max_y),
                            fill=(0, 255, 0, 100),
                        )
                else:
                    # sort by distance
                    match_candidates = sorted(
                        match_candidates,
                        key=lambda k: curr_state.distance(k.last_state()),
                    )
                    current_tracked_observation = match_candidates[0]
                    current_tracked_observation.push_state(curr_state)

                # draw rect around left foot
                if left_foot_x and left_foot_y and left_knee_x and left_knee_y:
                    rect_size = math.sqrt(
                        (left_foot_x - left_knee_x) ** 2
                        + (left_foot_y - left_knee_y) ** 2
                    )
                    draw.rectangle(
                        (
                            left_foot_x - rect_size / 2,
                            left_foot_y - rect_size / 2,
                            left_foot_x + rect_size / 2,
                            left_foot_y + rect_size / 2,
                        ),
                        outline=(255, 0, 130, 255),
                        width=2,
                    )

                    # extract foot image
                    foot_img = img.crop(
                        (
                            left_foot_x - rect_size / 2,
                            left_foot_y - rect_size / 2,
                            left_foot_x + rect_size / 2,
                            left_foot_y + rect_size / 2,
                        )
                    )
                    # encode as base64 data
                    buffered = BytesIO()
                    foot_img.save(buffered, format="JPEG")
                    img_str = base64.b64encode(buffered.getvalue())
                    if current_tracked_observation is not None:
                        current_tracked_observation.foot_image_data = (
                            bytes("data:image/jpeg;base64,", encoding="utf-8") + img_str
                        ).decode("utf-8")
                        # filtered_tracked_observations = [
                        #     obs for obs in tracked_observations if obs.age > 10
                        # ]
                        # send_json(
                        #     {
                        #         "type": "foot_photos",
                        #         "values": [
                        #             obs.foot_image_data
                        #             for obs in filtered_tracked_observations
                        #         ],
                        #     }
                        # )

            # sort observations by bb_min_x
            observations_data = sorted(
                observations_data, key=lambda k: k["bb_min_x"], reverse=True
            )
            # send_json(
            #     {
            #         "type": "observations",
            #         "observations": observations_data,
            #         "width": img.size[0],
            #         "height": img.size[1],
            #     }
            # )
            # sort tracked observations by bb_min_x
            tracked_observations.sort(
                key=lambda k: k.last_state().bb_center_x, reverse=True
            )

            # filtered_tracked_observations = [
            #     obs for obs in tracked_observations if obs.age > 10
            # ]
            # send_json(
            #     {
            #         "type": "tracked_observations",
            #         "values": [
            #             obs.last_foot_diff() for obs in filtered_tracked_observations
            #         ],
            #     }
            # )
            # print(obs.recognizedPointsSpecifier())

            # print methods available on the observation
            # print(obs.valueAtIndex_inPropertyWithKey_(0, "recognizedPoints"))
            # membe = inspect.getmembers(obs)
            # for m in membe:
            #     print(m)
            # print(obs.stringValueSafe())
            # print(obs.recognizedPointsSpecifier())
            # recognized_text = text_observation.topCandidates_(1)[0]
            # results.append([recognized_text.string(), recognized_text.confidence()])

    # draw min bb height as white line top right
    draw.line(
        (img.size[0] - 10, 0, img.size[0] - 10, calibration_config["min_bb_height"]),
        fill=(0, 0, 0, 255),
        width=3,
    )

    # draw min bb width as white line bottom left
    draw.line(
        (0, img.size[1] - 10, calibration_config["min_bb_width"], img.size[1] - 10),
        fill=(0, 0, 0, 255),
        width=3,
    )
    # draw deadzones
    draw.rectangle(
        (0, 0, calibration_config["left_deadzone"], img.size[1]),
        fill=(0, 0, 0, 100),
    )
    draw.rectangle(
        (
            img.size[0] - calibration_config["right_deadzone"],
            0,
            img.size[0],
            img.size[1],
        ),
        fill=(0, 0, 0, 100),
    )

    # tick tracked observations
    for obs in tracked_observations:
        obs.age += 1
        obs.time_since_last_match += 1
        if obs.time_since_last_match > 10:
            tracked_observations.remove(obs)
            continue
        obs.draw_history()

    return handler


def capture_shit():
    session = AVFoundation.AVCaptureSession.alloc().init()
    devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_(
        AVFoundation.AVMediaTypeVideo
    )
    device = devices[0]

    input_session = AVFoundation.AVCaptureDeviceInput.deviceInputWithDevice_error_(
        device, None
    )[0]

    session.addInput_(input_session)

    session.startRunning()


def main():
    import pathlib
    import sys

    # img_path = pathlib.Path(sys.argv[1])
    # if not img_path.is_file():
    #     sys.exit("Invalid image path")
    # img_path = str(img_path.resolve())
    # img = Image.open(img_path)
    # draw = ImageDraw.Draw(img)
    # detect_points(img_path)
    # img.show()

    load_calibration()

    img_path = "/tmp/ddd.jpg"
    cap = cv2.VideoCapture(0)

    while cap.isOpened():
        # Read a new frame
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("PoseCamera", frame)
        cv2.imwrite(img_path, frame)
        global img, draw

        img = Image.open(img_path)
        draw = ImageDraw.Draw(img, "RGBA")

        detect_points(img_path)

        # send data to websocket

        filtered_tracked_observations = [
            obs for obs in tracked_observations if obs.age > 15
        ]

        if len(filtered_tracked_observations) > 0:
            # sort by highest last_height
            filtered_tracked_observations = sorted(
                filtered_tracked_observations,
                key=lambda k: k.last_height(),
                reverse=True,
            )
            primary = filtered_tracked_observations[0]
            secondary = None

            if len(filtered_tracked_observations) > 1:
                # ensure second player is at least 80% of the height of the primary
                if (
                    filtered_tracked_observations[1].last_height()
                    > primary.last_height() * 0.8
                ):
                    secondary = filtered_tracked_observations[1]

            if primary is not None and secondary is not None:
                if primary.last_bb_center_x() > secondary.last_bb_center_x():
                    temp = primary
                    primary = secondary
                    secondary = temp

            primary_json = {
                "uuid": primary.uuid,
                "foot_diff": primary.last_foot_diff(),
                "foot_image_data":  primary.foot_image_data,
            }
            secondary_json = None
            if secondary is not None:
                secondary_json = {
                    "uuid": secondary.uuid,
                    "foot_diff": secondary.last_foot_diff(),
                    "foot_image_data": secondary.foot_image_data,
                }
            send_json(
                {
                    "type": "players",
                    "primary": primary_json,
                    "secondary": secondary_json,
                }
            )

        else:
            send_json(
                {
                    "type": "players",
                    "primary": None,
                    "secondary": None,
                }
            )

        nimg = np.array(img.convert("RGB"))
        ocvim = cv2.cvtColor(nimg, cv2.COLOR_RGB2BGR)
        # ocvim = nimg[:, :, ::-1].copy()

        cv2.imshow("PoseCamera", ocvim)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        with evt_queue_lock:
            while not evt_queue.empty():
                evt = evt_queue.get()
                if evt["type"] == "adjust_min_bb_height":
                    calibration_config["min_bb_height"] += evt["delta"]
                    if calibration_config["min_bb_height"] < 0:
                        calibration_config["min_bb_height"] = 0
                    save_calibration()
                if evt["type"] == "adjust_min_bb_width":
                    calibration_config["min_bb_width"] += evt["delta"]
                    if calibration_config["min_bb_width"] < 0:
                        calibration_config["min_bb_width"] = 0
                    save_calibration()
                if evt["type"] == "adjust_left_deadzone":
                    calibration_config["left_deadzone"] += evt["delta"]
                    if calibration_config["left_deadzone"] < 0:
                        calibration_config["left_deadzone"] = 0
                    save_calibration()
                if evt["type"] == "adjust_right_deadzone":
                    calibration_config["right_deadzone"] += evt["delta"]
                    if calibration_config["right_deadzone"] < 0:
                        calibration_config["right_deadzone"] = 0
                    save_calibration()

    cap.release()
    cv2.destroyAllWindows()

    # cap = cv2.VideoCapture(0)

    # while cap.isOpened():
    #     # Read a new frame
    #     ret, frame = cap.read()
    #     if not ret:
    #         break

    #     img_path = "/tmp/img.jpg"
    #     # save the frame
    #     cv2.imshow('Frame', frame)
    #     # img = Image.open(img_path)
    #     # draw = ImageDraw.Draw(img)
    #     # detect_points(img_path)

    #     # img.show()
    # sys.exit(1)


if __name__ == "__main__":
    main()
