import cv2
import numpy as np
import time
import os
import signal
import sys

class OBJModel:
    def __init__(self, filename):
        self.vertices = []
        self.faces = []
        self.load_obj(filename)
        
    def load_obj(self, filename):
        """Load OBJ file with vertices and faces"""
        try:
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('v '):
                        parts = line.strip().split()
                        self.vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                    elif line.startswith('f '):
                        parts = line.strip().split()
                        face = []
                        for part in parts[1:]:
                            idx = part.split('/')[0]
                            if idx:
                                face.append(int(idx) - 1)
                        if len(face) >= 3:
                            self.faces.append(face)
            
            self.vertices = np.array(self.vertices, dtype=np.float32)
            print(f"✅ Loaded {len(self.vertices)} vertices, {len(self.faces)} faces")
            
        except Exception as e:
            print(f"❌ Error loading OBJ: {e}")
    
    def transform(self, scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z):
        """Apply transformations to vertices"""
        if len(self.vertices) == 0:
            return None
            
        transformed = self.vertices.copy()
        
        # Scale
        transformed *= scale
        
        # Rotation matrices
        if rot_x != 0:
            rad = np.radians(rot_x)
            rot_x_mat = np.array([
                [1, 0, 0],
                [0, np.cos(rad), -np.sin(rad)],
                [0, np.sin(rad), np.cos(rad)]
            ])
            transformed = transformed @ rot_x_mat.T
        
        if rot_y != 0:
            rad = np.radians(rot_y)
            rot_y_mat = np.array([
                [np.cos(rad), 0, np.sin(rad)],
                [0, 1, 0],
                [-np.sin(rad), 0, np.cos(rad)]
            ])
            transformed = transformed @ rot_y_mat.T
        
        if rot_z != 0:
            rad = np.radians(rot_z)
            rot_z_mat = np.array([
                [np.cos(rad), -np.sin(rad), 0],
                [np.sin(rad), np.cos(rad), 0],
                [0, 0, 1]
            ])
            transformed = transformed @ rot_z_mat.T
        
        # Translation
        transformed[:, 0] += offset_x
        transformed[:, 1] += offset_y
        transformed[:, 2] += offset_z
        
        return transformed

def nothing(x):
    pass

def signal_handler(sig, frame):
    print("\n👋 Exiting gracefully...")
    cv2.destroyAllWindows()
    sys.exit(0)

# def open_camera():
#     """Try multiple methods to open camera"""
    
#     methods = [
#         # Method 1: Simple V4L2
#         (cv2.CAP_V4L2, 0, "V4L2"),
        
#         # Method 2: Simple default
#         (cv2.CAP_ANY, 0, "Default"),
        
#         # Method 3: GStreamer with simple pipeline
#         (cv2.CAP_GSTREAMER, "v4l2src device=/dev/video0 ! videoconvert ! appsink", "GStreamer simple"),
#     ]
    
#     for backend, param, name in methods:
#         try:
#             if backend == cv2.CAP_GSTREAMER:
#                 cap = cv2.VideoCapture(param, backend)
#             else:
#                 cap = cv2.VideoCapture(param, backend)
            
#             if cap.isOpened():
#                 # Set timeout and try to read a frame
#                 cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
#                 ret, frame = cap.read()
#                 if ret and frame is not None:
#                     print(f"✅ Camera opened with: {name}")
#                     cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
#                     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
#                     return cap
#                 else:
#                     cap.release()
#         except Exception as e:
#             continue
    
#     print("❌ All camera methods failed")
#     return None

def open_camera():
    """Simplest camera open"""
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Проверим, что читается кадр
            ret, frame = cap.read()
            if ret and frame is not None:
                print("✅ Camera opened with V4L2")
                return cap
    except:
        pass
    
    # Если не получилось, пробуем без бэкенда
    try:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print("✅ Camera opened with default backend")
            return cap
    except:
        pass
    
    return None
    

def main():
    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load model
    print("Loading model...")
    model = OBJModel("model_simple.obj")
    if len(model.vertices) == 0:
        print("Failed to load model")
        return
    
    # Try to open camera
    print("\n🔍 Attempting to open camera...")
    cap = open_camera()
    
    if cap is None:
        print("\n⚠️  Using black background (no camera)")
        use_camera = False
        width, height = 1280, 720
    else:
        use_camera = True
        # Get actual camera resolution
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width == 0 or height == 0:
            width, height = 640, 480
        print(f"📷 Camera resolution: {width}x{height}")
    
    # Camera parameters
    camera_matrix = np.array([
        [800, 0, width//2],
        [0, 800, height//2],
        [0, 0, 1]
    ], dtype=np.float32)
    
    # Camera position
    rvec = np.array([[0.], [0.], [0.]], dtype=np.float32)
    tvec = np.array([[0.], [0.], [0.]], dtype=np.float32)
    
    # Create window
    window_name = 'OBJ Model Viewer'
    cv2.namedWindow(window_name)
    
    # Create trackbars
    cv2.createTrackbar('Scale', window_name, 30, 100, nothing)
    cv2.createTrackbar('Rot X', window_name, 180, 360, nothing)
    cv2.createTrackbar('Rot Y', window_name, 180, 360, nothing)
    cv2.createTrackbar('Rot Z', window_name, 180, 360, nothing)
    cv2.createTrackbar('Offset X', window_name, 500, 1000, nothing)
    cv2.createTrackbar('Offset Y', window_name, 500, 1000, nothing)
    cv2.createTrackbar('Offset Z', window_name, 300, 1000, nothing)
    cv2.createTrackbar('Mode: 0pts/1wire/2face', window_name, 0, 2, nothing)
    
    # Pre-compute edges
    print("Pre-computing edges...")
    edges = set()
    for face in model.faces:
        for i in range(len(face)):
            edge = tuple(sorted((face[i], face[(i+1) % len(face)])))
            edges.add(edge)
    edges = list(edges)
    print(f"✅ Computed {len(edges)} edges")
    
    print("\n" + "="*50)
    print("CAMERA VIEWER CONTROLS:")
    print("="*50)
    print("🎚️ Use SLIDERS to adjust model position")
    print("🎯 Mode slider: 0=points, 1=wireframe, 2=faces")
    print("\n⌨️ Keyboard:")
    print("  R - reset sliders")
    print("  P - print settings")
    print("  ESC or Ctrl+C - exit")
    print("="*50 + "\n")
    
    # For FPS calculation
    last_time = time.time()
    frame_count = 0
    fps = 0
    
    try:
        while True:
            frame_count += 1
            if frame_count % 10 == 0:
                current_time = time.time()
                fps = 10 / (current_time - last_time)
                last_time = current_time
            
            # Get camera frame with timeout
            if use_camera:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️ Failed to grab frame, using black background")
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
            else:
                frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Get values from trackbars
            scale = cv2.getTrackbarPos('Scale', window_name) / 100.0
            rot_x = cv2.getTrackbarPos('Rot X', window_name) - 180
            rot_y = cv2.getTrackbarPos('Rot Y', window_name) - 180
            rot_z = cv2.getTrackbarPos('Rot Z', window_name) - 180
            offset_x = (cv2.getTrackbarPos('Offset X', window_name) - 500) / 10.0
            offset_y = (cv2.getTrackbarPos('Offset Y', window_name) - 500) / 10.0
            offset_z = cv2.getTrackbarPos('Offset Z', window_name) / 10.0
            mode = cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_name)
            
            # Handle keyboard
            key = cv2.waitKey(1) & 0xFF
            
            if key == 27:  # ESC
                break
            elif key == ord('r'):  # reset
                cv2.setTrackbarPos('Scale', window_name, 30)
                cv2.setTrackbarPos('Rot X', window_name, 180)
                cv2.setTrackbarPos('Rot Y', window_name, 180)
                cv2.setTrackbarPos('Rot Z', window_name, 180)
                cv2.setTrackbarPos('Offset X', window_name, 500)
                cv2.setTrackbarPos('Offset Y', window_name, 500)
                cv2.setTrackbarPos('Offset Z', window_name, 300)
                cv2.setTrackbarPos('Mode: 0pts/1wire/2face', window_name, 0)
                print("🔄 Reset to default")
            elif key == ord('p'):  # print settings
                print(f"\n=== CURRENT SETTINGS ===")
                print(f"scale = {scale:.3f}")
                print(f"rot_x = {rot_x}")
                print(f"rot_y = {rot_y}")
                print(f"rot_z = {rot_z}")
                print(f"offset_x = {offset_x:.3f}")
                print(f"offset_y = {offset_y:.3f}")
                print(f"offset_z = {offset_z:.3f}")
                print(f"mode = {mode}")
                print("========================\n")
            
            # Transform vertices
            transformed = model.transform(scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z)
            
            if transformed is not None:
                # Project all vertices
                img_points, _ = cv2.projectPoints(transformed, rvec, tvec, camera_matrix, None)
                img_points = np.int32(img_points).reshape(-1, 2)
                
                # Render based on mode
                if mode == 0:  # Points only
                    for pt in img_points:
                        if 0 <= pt[0] < width and 0 <= pt[1] < height:
                            cv2.circle(frame, tuple(pt), 2, (0, 255, 255), -1)
                
                elif mode == 1:  # Wireframe
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 0), 1)
                    
                    for pt in img_points:
                        if 0 <= pt[0] < width and 0 <= pt[1] < height:
                            cv2.circle(frame, tuple(pt), 1, (0, 255, 255), -1)
                
                else:  # mode == 2, Faces
                    for i, face in enumerate(model.faces):
                        if i % 3 != 0:
                            continue
                        if len(face) >= 3:
                            pts = []
                            valid = True
                            for idx in face[:3]:
                                if idx < len(img_points):
                                    pt = img_points[idx]
                                    if 0 <= pt[0] < width and 0 <= pt[1] < height:
                                        pts.append([pt[0], pt[1]])
                                    else:
                                        valid = False
                                        break
                            
                            if valid and len(pts) == 3:
                                pts = np.array(pts, np.int32)
                                cv2.fillPoly(frame, [pts], (100, 100, 255))
                    
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 255), 1)
            
            # Draw info panel
            mode_names = ["POINTS", "WIREFRAME", "FACES"]
            camera_status = "📷 LIVE" if use_camera else "⚫ NO CAMERA"
            info = [
                f"FPS: {fps:.1f} | {camera_status}",
                f"Scale: {scale:.2f}",
                f"Rot X/Y/Z: {rot_x:3d} {rot_y:3d} {rot_z:3d}",
                f"Offset X/Y/Z: {offset_x:.2f} {offset_y:.2f} {offset_z:.2f}",
                f"Mode: {mode_names[mode]}",
            ]
            
            for i, text in enumerate(info):
                cv2.putText(frame, text, (10, 30 + i*25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Instructions
            cv2.putText(frame, "R:reset | P:print | ESC/Ctrl+C:exit", 
                       (10, height-20), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, (150, 150, 150), 1)
            
            cv2.imshow(window_name, frame)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\n👋 Cleaning up...")
        if use_camera:
            cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()