"""
Детектор AprilTag маркеров - ТОЧНАЯ КОПИЯ ИСХОДНОГО КОДА
"""
import numpy as np
import cv2
from pyapriltags import Detector
from src.utils.math_utils import flip_z_axis, rotation_vector_to_euler


class AprilTagDetector:
    def __init__(self, config: dict):
        self.config = config
        self.family = config['family']
        self.target_id = config['target_id']
        self.size_mm = config['size_mm']
        self.size_m = self.size_mm / 1000.0
        
        detector_config = config['detector']
        self.detector = Detector(
            families=self.family,
            nthreads=detector_config['nthreads'],
            quad_decimate=detector_config['quad_decimate'],
            quad_sigma=detector_config['quad_sigma'],
            refine_edges=detector_config['refine_edges'],
            decode_sharpening=detector_config['decode_sharpening'],
            debug=detector_config.get('debug', 0)
        )
    
    def detect(self, gray_frame, camera_matrix, dist_coeffs):
        """
        Детектирование AprilTag маркеров - ТОЧНО КАК В ИСХОДНОМ КОДЕ
        """
        detections = self.detector.detect(
            gray_frame,
            estimate_tag_pose=True,
            camera_params=[
                camera_matrix[0,0],
                camera_matrix[1,1],
                camera_matrix[0,2],
                camera_matrix[1,2]
            ],
            tag_size=self.size_m
        )
        
        target_rvec = None
        target_tvec = None
        target_corners = None
        tag_info = "No tag detected"
        
        for detection in detections:
            corners = np.array(detection.corners, dtype=np.int32)
            color = (0,255,255) if detection.tag_id == self.target_id else (0,255,0)
            
            rvec, _ = cv2.Rodrigues(detection.pose_R)
            tvec = np.array(detection.pose_t).reshape(3, 1)
            rvec, tvec = flip_z_axis(rvec, tvec)
            
            if detection.tag_id == self.target_id:
                target_rvec = rvec
                target_tvec = tvec
                target_corners = np.array(detection.corners, dtype=np.float32)
                
                roll, pitch, yaw = rotation_vector_to_euler(rvec)
                distance = np.linalg.norm(tvec)
                tag_info = (f"Tag ID:{detection.tag_id} | D:{distance:.2f}m | "
                           f"R:{roll:.1f} P:{pitch:.1f} Y:{yaw:.1f}")
                
                break
        
        return target_rvec, target_tvec, target_corners, tag_info