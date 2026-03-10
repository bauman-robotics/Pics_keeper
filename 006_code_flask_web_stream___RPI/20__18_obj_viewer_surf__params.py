import cv2
import numpy as np
import time
import os
import signal
import sys
import json

class OBJModel:
    def __init__(self, filename):
        self.vertices = []
        self.faces = []
        self.filename = filename
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
            
            # Calculate model statistics
            self.min_bounds = np.min(self.vertices, axis=0)
            self.max_bounds = np.max(self.vertices, axis=0)
            self.center = (self.min_bounds + self.max_bounds) / 2
            self.size = self.max_bounds - self.min_bounds
            self.diagonal = np.linalg.norm(self.size)
            
            print(f"\n{'='*50}")
            print(f"📊 MODEL STATISTICS: {filename}")
            print(f"{'='*50}")
            print(f"✅ Loaded {len(self.vertices)} vertices, {len(self.faces)} faces")
            print(f"\n📐 BOUNDING BOX:")
            print(f"   Min: ({self.min_bounds[0]:.3f}, {self.min_bounds[1]:.3f}, {self.min_bounds[2]:.3f})")
            print(f"   Max: ({self.max_bounds[0]:.3f}, {self.max_bounds[1]:.3f}, {self.max_bounds[2]:.3f})")
            print(f"   Center: ({self.center[0]:.3f}, {self.center[1]:.3f}, {self.center[2]:.3f})")
            print(f"   Size (WxHxD): {self.size[0]:.3f} x {self.size[1]:.3f} x {self.size[2]:.3f}")
            print(f"   Diagonal: {self.diagonal:.3f}")
            print(f"{'='*50}\n")
            
        except Exception as e:
            print(f"❌ Error loading OBJ: {e}")
    
    def get_model_info(self):
        """Return model statistics as formatted string"""
        return (f"Model: {os.path.basename(self.filename)}\n"
                f"Vertices: {len(self.vertices)} | Faces: {len(self.faces)}\n"
                f"Size: {self.size[0]:.2f} x {self.size[1]:.2f} x {self.size[2]:.2f}\n"
                f"Center: ({self.center[0]:.2f}, {self.center[1]:.2f}, {self.center[2]:.2f})")
    
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

class Button:
    def __init__(self, x, y, width, height, text, color=(100, 100, 200), hover_color=(150, 150, 255)):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False
        self.is_pressed = False
        
    def draw(self, frame):
        color = self.hover_color if self.is_hovered else self.color
        # Draw button
        cv2.rectangle(frame, (self.x, self.y), (self.x + self.width, self.y + self.height), color, -1)
        cv2.rectangle(frame, (self.x, self.y), (self.x + self.width, self.y + self.height), (255, 255, 255), 2)
        
        # Draw text
        text_size = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        text_x = self.x + (self.width - text_size[0]) // 2
        text_y = self.y + (self.height + text_size[1]) // 2
        cv2.putText(frame, self.text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
    def is_inside(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

class ModeButton(Button):
    def __init__(self, x, y, width, height, text, mode_id, color=(100, 200, 100), hover_color=(150, 255, 150)):
        super().__init__(x, y, width, height, text, color, hover_color)
        self.mode_id = mode_id
        self.is_active = False
        
    def draw(self, frame):
        color = self.hover_color if self.is_hovered else self.color
        if self.is_active:
            # Draw brighter border for active button
            cv2.rectangle(frame, (self.x-2, self.y-2), (self.x + self.width+2, self.y + self.height+2), (255, 255, 0), 3)
        
        # Draw button
        cv2.rectangle(frame, (self.x, self.y), (self.x + self.width, self.y + self.height), color, -1)
        cv2.rectangle(frame, (self.x, self.y), (self.x + self.width, self.y + self.height), (255, 255, 255), 2)
        
        # Draw text
        text_size = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        text_x = self.x + (self.width - text_size[0]) // 2
        text_y = self.y + (self.height + text_size[1]) // 2
        cv2.putText(frame, self.text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

def nothing(x):
    pass

def signal_handler(sig, frame):
    print("\n👋 Exiting gracefully...")
    cv2.destroyAllWindows()
    sys.exit(0)

def open_camera():
    """Simplest camera open"""
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Check if we can read a frame
            ret, frame = cap.read()
            if ret and frame is not None:
                print("✅ Camera opened with V4L2")
                return cap
    except:
        pass
    
    # If failed, try without backend
    try:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print("✅ Camera opened with default backend")
            return cap
    except:
        pass
    
    return None

def print_model_position(model, scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z):
    """Print current model position and transformation details"""
    transformed = model.transform(scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z)
    if transformed is not None:
        min_pos = np.min(transformed, axis=0)
        max_pos = np.max(transformed, axis=0)
        center_pos = (min_pos + max_pos) / 2
        size_pos = max_pos - min_pos
        
        print(f"\n{'='*50}")
        print(f"📍 CURRENT MODEL POSITION IN WORLD")
        print(f"{'='*50}")
        print(f"\n📐 TRANSFORMATIONS:")
        print(f"   Scale: {scale:.3f}")
        print(f"   Rotation (X,Y,Z): ({rot_x:3d}°, {rot_y:3d}°, {rot_z:3d}°)")
        print(f"   Translation (X,Y,Z): ({offset_x:.3f}, {offset_y:.3f}, {offset_z:.3f})")
        
        print(f"\n📦 MODEL BOUNDING BOX (after transforms):")
        print(f"   Min: ({min_pos[0]:.3f}, {min_pos[1]:.3f}, {min_pos[2]:.3f})")
        print(f"   Max: ({max_pos[0]:.3f}, {max_pos[1]:.3f}, {max_pos[2]:.3f})")
        print(f"   Center: ({center_pos[0]:.3f}, {center_pos[1]:.3f}, {center_pos[2]:.3f})")
        print(f"   Size: {size_pos[0]:.3f} x {size_pos[1]:.3f} x {size_pos[2]:.3f}")
        print(f"   Diagonal: {np.linalg.norm(size_pos):.3f}")
        
        # Camera view info
        print(f"\n🎯 CAMERA VIEW:")
        print(f"   Distance from origin: {np.linalg.norm(center_pos):.3f}")
        print(f"   X range: [{min_pos[0]:.3f}, {max_pos[0]:.3f}]")
        print(f"   Y range: [{min_pos[1]:.3f}, {max_pos[1]:.3f}]")
        print(f"   Z range: [{min_pos[2]:.3f}, {max_pos[2]:.3f}]")
        print(f"{'='*50}\n")

def save_position(filename="model_position.json", scale=None, rot_x=None, rot_y=None, rot_z=None, 
                  offset_x=None, offset_y=None, offset_z=None, mode=None):
    """Save current slider positions to JSON file"""
    position_data = {
        "scale": scale,
        "rot_x": rot_x,
        "rot_y": rot_y,
        "rot_z": rot_z,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "offset_z": offset_z,
        "mode": mode,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        with open(filename, 'w') as f:
            json.dump(position_data, f, indent=4)
        print(f"\n💾 Position saved to {filename}")
        print(f"   Scale: {scale:.3f}")
        print(f"   Rotation: ({rot_x}°, {rot_y}°, {rot_z}°)")
        print(f"   Offset: ({offset_x:.3f}, {offset_y:.3f}, {offset_z:.3f})")
        print(f"   Mode: {mode}")
        return True
    except Exception as e:
        print(f"❌ Error saving position: {e}")
        return False

def load_position(filename="model_position.json"):
    """Load slider positions from JSON file"""
    try:
        if not os.path.exists(filename):
            print(f"\n⚠️ Position file {filename} not found")
            return None
            
        with open(filename, 'r') as f:
            position_data = json.load(f)
        
        print(f"\n📂 Position loaded from {filename}")
        print(f"   Timestamp: {position_data.get('timestamp', 'unknown')}")
        print(f"   Scale: {position_data.get('scale', 0.3):.3f}")
        print(f"   Rotation: ({position_data.get('rot_x', 0)}°, {position_data.get('rot_y', 0)}°, {position_data.get('rot_z', 0)}°)")
        print(f"   Offset: ({position_data.get('offset_x', 0):.3f}, {position_data.get('offset_y', 0):.3f}, {position_data.get('offset_z', 0):.3f})")
        print(f"   Mode: {position_data.get('mode', 0)}")
        
        return position_data
    except Exception as e:
        print(f"❌ Error loading position: {e}")
        return None

def mouse_callback(event, x, y, flags, param):
    """Handle mouse events for buttons"""
    buttons = param['buttons']
    mode_buttons = param['mode_buttons']
    
    # Update hover states
    for button in buttons + mode_buttons:
        button.is_hovered = button.is_inside(x, y)
    
    # Handle clicks
    if event == cv2.EVENT_LBUTTONDOWN:
        for button in buttons:
            if button.is_inside(x, y):
                button.is_pressed = True
                if button.text == "RESET":
                    # Reset all trackbars
                    cv2.setTrackbarPos('Scale', param['window_name'], 30)
                    cv2.setTrackbarPos('Rot X', param['window_name'], 180)
                    cv2.setTrackbarPos('Rot Y', param['window_name'], 180)
                    cv2.setTrackbarPos('Rot Z', param['window_name'], 180)
                    cv2.setTrackbarPos('Offset X', param['window_name'], 500)
                    cv2.setTrackbarPos('Offset Y', param['window_name'], 500)
                    cv2.setTrackbarPos('Offset Z', param['window_name'], 300)
                    print("🔄 Reset to default")
                elif button.text == "PRINT":
                    # Print current position
                    print_model_position(
                        param['model'],
                        param['get_values'][0](),  # scale
                        param['get_values'][1](),  # rot_x
                        param['get_values'][2](),  # rot_y
                        param['get_values'][3](),  # rot_z
                        param['get_values'][4](),  # offset_x
                        param['get_values'][5](),  # offset_y
                        param['get_values'][6]()   # offset_z
                    )
                elif button.text == "INFO":
                    # Print model info
                    print(f"\n{param['model'].get_model_info()}\n")
                elif button.text == "SAVE":
                    # Save current position
                    save_position(
                        scale=param['get_values'][0](),
                        rot_x=param['get_values'][1](),
                        rot_y=param['get_values'][2](),
                        rot_z=param['get_values'][3](),
                        offset_x=param['get_values'][4](),
                        offset_y=param['get_values'][5](),
                        offset_z=param['get_values'][6](),
                        mode=cv2.getTrackbarPos('Mode: 0pts/1wire/2face', param['window_name'])
                    )
                elif button.text == "LOAD":
                    # Load position
                    position_data = load_position()
                    if position_data:
                        # Convert and set trackbars
                        cv2.setTrackbarPos('Scale', param['window_name'], int(position_data.get('scale', 0.3) * 100))
                        cv2.setTrackbarPos('Rot X', param['window_name'], position_data.get('rot_x', 0) + 180)
                        cv2.setTrackbarPos('Rot Y', param['window_name'], position_data.get('rot_y', 0) + 180)
                        cv2.setTrackbarPos('Rot Z', param['window_name'], position_data.get('rot_z', 0) + 180)
                        cv2.setTrackbarPos('Offset X', param['window_name'], int(position_data.get('offset_x', 0) * 10 + 500))
                        cv2.setTrackbarPos('Offset Y', param['window_name'], int(position_data.get('offset_y', 0) * 10 + 500))
                        cv2.setTrackbarPos('Offset Z', param['window_name'], int(position_data.get('offset_z', 0) * 10))
                        cv2.setTrackbarPos('Mode: 0pts/1wire/2face', param['window_name'], position_data.get('mode', 0))
                elif button.text == "EXIT":
                    # Exit
                    param['running'] = False
        
        # Handle mode buttons
        for mode_button in mode_buttons:
            if mode_button.is_inside(x, y):
                cv2.setTrackbarPos('Mode: 0pts/1wire/2face', param['window_name'], mode_button.mode_id)
    
    elif event == cv2.EVENT_LBUTTONUP:
        for button in buttons:
            button.is_pressed = False

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
    
    # Create trackbars (keep them for fine adjustment)
    cv2.createTrackbar('Scale', window_name, 30, 100, nothing)
    cv2.createTrackbar('Rot X', window_name, 180, 360, nothing)
    cv2.createTrackbar('Rot Y', window_name, 180, 360, nothing)
    cv2.createTrackbar('Rot Z', window_name, 180, 360, nothing)
    cv2.createTrackbar('Offset X', window_name, 500, 1000, nothing)
    cv2.createTrackbar('Offset Y', window_name, 500, 1000, nothing)
    cv2.createTrackbar('Offset Z', window_name, 300, 1000, nothing)
    cv2.createTrackbar('Mode: 0pts/1wire/2face', window_name, 0, 2, nothing)
    
    # Create buttons
    button_width = 90
    button_height = 40
    button_margin = 5
    start_x = width - (button_width + button_margin) * 6
    
    # Function to get current values from trackbars
    def get_scale():
        return cv2.getTrackbarPos('Scale', window_name) / 100.0
    
    def get_rot_x():
        return cv2.getTrackbarPos('Rot X', window_name) - 180
    
    def get_rot_y():
        return cv2.getTrackbarPos('Rot Y', window_name) - 180
    
    def get_rot_z():
        return cv2.getTrackbarPos('Rot Z', window_name) - 180
    
    def get_offset_x():
        return (cv2.getTrackbarPos('Offset X', window_name) - 500) / 10.0
    
    def get_offset_y():
        return (cv2.getTrackbarPos('Offset Y', window_name) - 500) / 10.0
    
    def get_offset_z():
        return cv2.getTrackbarPos('Offset Z', window_name) / 10.0
    
    # Create action buttons
    buttons = [
        Button(start_x, 10, button_width, button_height, "RESET", (50, 50, 200), (100, 100, 255)),
        Button(start_x + button_width + button_margin, 10, button_width, button_height, "PRINT", (50, 150, 50), (100, 200, 100)),
        Button(start_x + (button_width + button_margin) * 2, 10, button_width, button_height, "INFO", (150, 150, 50), (200, 200, 100)),
        Button(start_x + (button_width + button_margin) * 3, 10, button_width, button_height, "SAVE", (50, 100, 150), (100, 150, 200)),
        Button(start_x + (button_width + button_margin) * 4, 10, button_width, button_height, "LOAD", (100, 50, 150), (150, 100, 200)),
        Button(start_x + (button_width + button_margin) * 5, 10, button_width, button_height, "EXIT", (200, 50, 50), (255, 100, 100))
    ]
    
    # Create mode buttons
    mode_buttons = [
        ModeButton(10, height - 60, 80, 40, "POINTS", 0, (100, 100, 200), (150, 150, 255)),
        ModeButton(100, height - 60, 100, 40, "WIREFRAME", 1, (100, 200, 100), (150, 255, 150)),
        ModeButton(210, height - 60, 80, 40, "FACES", 2, (200, 100, 100), (255, 150, 150))
    ]
    
    # Set initial active mode
    mode_buttons[0].is_active = True
    
    # Mouse callback parameters
    mouse_params = {
        'buttons': buttons,
        'mode_buttons': mode_buttons,
        'window_name': window_name,
        'model': model,
        'get_values': [get_scale, get_rot_x, get_rot_y, get_rot_z, get_offset_x, get_offset_y, get_offset_z],
        'running': True
    }
    
    # Set mouse callback
    cv2.setMouseCallback(window_name, mouse_callback, mouse_params)
    
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
    print("🖱️ Use MOUSE to click buttons")
    print("🎚️ Use SLIDERS for fine adjustment")
    print("🎯 Mode buttons: POINTS, WIREFRAME, FACES")
    print("\n🖱️ BUTTONS:")
    print("  RESET - reset all sliders")
    print("  PRINT - print current position to console")
    print("  INFO - print model statistics")
    print("  SAVE - save current position to model_position.json")
    print("  LOAD - load position from model_position.json")
    print("  EXIT - exit program")
    print("="*50 + "\n")
    
    # Try to auto-load position if exists
    position_data = load_position()
    if position_data:
        print("\n🔄 Auto-loading previous position...")
        cv2.setTrackbarPos('Scale', window_name, int(position_data.get('scale', 0.3) * 100))
        cv2.setTrackbarPos('Rot X', window_name, position_data.get('rot_x', 0) + 180)
        cv2.setTrackbarPos('Rot Y', window_name, position_data.get('rot_y', 0) + 180)
        cv2.setTrackbarPos('Rot Z', window_name, position_data.get('rot_z', 0) + 180)
        cv2.setTrackbarPos('Offset X', window_name, int(position_data.get('offset_x', 0) * 10 + 500))
        cv2.setTrackbarPos('Offset Y', window_name, int(position_data.get('offset_y', 0) * 10 + 500))
        cv2.setTrackbarPos('Offset Z', window_name, int(position_data.get('offset_z', 0) * 10))
        cv2.setTrackbarPos('Mode: 0pts/1wire/2face', window_name, position_data.get('mode', 0))
    
    # For FPS calculation
    last_time = time.time()
    frame_count = 0
    fps = 0
    
    try:
        while mouse_params['running']:
            frame_count += 1
            if frame_count % 10 == 0:
                current_time = time.time()
                fps = 10 / (current_time - last_time)
                last_time = current_time
            
            # Get camera frame
            if use_camera:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️ Failed to grab frame, using black background")
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
            else:
                frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Get values from trackbars
            scale = get_scale()
            rot_x = get_rot_x()
            rot_y = get_rot_y()
            rot_z = get_rot_z()
            offset_x = get_offset_x()
            offset_y = get_offset_y()
            offset_z = get_offset_z()
            mode = cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_name)
            
            # Update mode buttons active state
            for i, mode_button in enumerate(mode_buttons):
                mode_button.is_active = (i == mode)
            
            # Handle keyboard (keep as backup)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            
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
            
            # Draw buttons
            for button in buttons:
                button.draw(frame)
            
            for mode_button in mode_buttons:
                mode_button.draw(frame)
            
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
            cv2.putText(frame, "SAVE/LOAD buttons use model_position.json", 
                       (10, height-10), cv2.FONT_HERSHEY_SIMPLEX, 
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