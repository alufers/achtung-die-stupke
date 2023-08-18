import posecamera
import cv2
import math
print("elo")
# Initialize PoseTracker
det = posecamera.pose_tracker.PoseTracker()

# Open the default camera
cap = cv2.VideoCapture(0)

def dist(x1, y1, x2, y2):
    return math.sqrt((x2-x1)**2 + (y2-y1)**2)

while cap.isOpened():
    # Read a new frame
    ret, frame = cap.read()
    if not ret:
        break

    # Process the frame through PoseTracker
    pose = det(frame)
    # get ankles
    left_ankle = pose.keypoints["left_ankle"]
    right_ankle = pose.keypoints["right_ankle"]
    left_knee = pose.keypoints["left_knee"]
    right_knee = pose.keypoints["right_knee"]
    # draw circle
    cv2.circle(frame, (int(left_ankle[1]), int(left_ankle[0])), 20, (255, 0, 255), -1)
    cv2.circle(frame, (int(right_ankle[1]), int(right_ankle[0])), 20, (255, 0, 255), -1)
    cv2.circle(frame, (int(left_knee[1]), int(left_knee[0])), 15, (255, 0, 0), -1)
    cv2.circle(frame, (int(right_knee[1]), int(right_knee[0])), 15, (255, 0, 0), -1)

    # calculate distance between right and left ankle
    left_dist = dist(left_ankle[1], left_ankle[0], left_knee[1], left_knee[0])
    right_dist = dist(right_ankle[1], right_ankle[0], right_knee[1], right_knee[0])

    # draw distance on screen
    cv2.putText(frame, str(left_dist), (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, str(right_dist), (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)
    
    # for name, (y, x, score) in pose.keypoints.items():
        # cv2.circle(frame, (int(x), int(y)), 20, (255, 0, 0), -1)

    # Display the results
    cv2.imshow("PoseCamera", frame)

    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
