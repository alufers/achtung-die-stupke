import cv2

cap = cv2.VideoCapture(0)

while cap.isOpened():
    # Read a new frame
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow("PoseCamera", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

