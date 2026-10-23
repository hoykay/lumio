import cv2

print("Lumio Camera Test")
print("OpenCV version:", cv2.__version__)

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("❌ Could not open camera.")
    exit()

print("✅ Camera opened successfully.")

while True:
    success, frame = camera.read()

    if not success:
        print("❌ Could not read frame.")
        break

    cv2.imshow("Lumio Camera Test", frame)

    # Press Q to close
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()