"""
Уточнение позы маркера с использованием дополнительных точек
"""
import numpy as np
import cv2


class PoseRefiner:
    """Уточнение позы с дополнительными точками"""
    
    def __init__(self, config: dict):
        self.config = config
        self.reproj_threshold = config['reproj_threshold']
    
    def refine(self, rvec_init, tvec_init, 
               apriltag_obj_pts, apriltag_img_pts,
               pyramid_results,
               camera_matrix, dist_coeffs):
        """
        Уточнение позы с использованием точек пирамиды
        
        Returns:
            rvec_refined, tvec_refined, n_extra_points, reproj_before, reproj_after
        """
        # Сбор дополнительных точек
        extra_obj = []
        extra_img = []
        weights = []
        
        for r in pyramid_results:
            if isinstance(r, dict):
                confidence = r.get('confidence', 1.0)
                if r.get('center_2d') is not None and confidence > 0.3:
                    extra_obj.append(r['center_3d'] / 1000.0)  # мм → м
                    extra_img.append(r['center_2d'])
                    weights.append(confidence)
        
        n_extra = len(extra_obj)
        
        if n_extra < 2:
            return rvec_init, tvec_init, 0, None, None
        
        # Объединение точек
        obj_pts_combined = np.vstack([
            apriltag_obj_pts / 1000.0,
            np.array(extra_obj, dtype=np.float32)
        ]).astype(np.float32)
        
        img_pts_tag = apriltag_img_pts.reshape(-1, 1, 2).astype(np.float32)
        img_pts_extra = np.array(extra_img, dtype=np.float32).reshape(-1, 1, 2)
        img_pts_combined = np.vstack([img_pts_tag, img_pts_extra])
        
        # Ошибка до уточнения
        proj_before, _ = cv2.projectPoints(
            obj_pts_combined, rvec_init, tvec_init, camera_matrix, dist_coeffs
        )
        errors_before = np.linalg.norm(
            proj_before.reshape(-1, 2) - img_pts_combined.reshape(-1, 2), axis=1
        )
        reproj_before = float(np.mean(errors_before))
        median_before = float(np.median(errors_before))
        
        # Уточнение
        try:
            # Пробуем RANSAC
            ret, rvec_ref, tvec_ref, inliers = cv2.solvePnPRansac(
                obj_pts_combined,
                img_pts_combined,
                camera_matrix,
                dist_coeffs,
                useExtrinsicGuess=True,
                rvec=rvec_init.copy(),
                tvec=tvec_init.copy(),
                iterationsCount=500,
                reprojectionError=10.0,
                confidence=0.99,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            
            if not ret or inliers is None or len(inliers) < 4:
                # Пробуем обычный PnP
                ret, rvec_ref, tvec_ref = cv2.solvePnP(
                    obj_pts_combined,
                    img_pts_combined,
                    camera_matrix,
                    dist_coeffs,
                    rvec=rvec_init.copy(),
                    tvec=tvec_init.copy(),
                    useExtrinsicGuess=True,
                    flags=cv2.SOLVEPNP_ITERATIVE
                )
                
                if not ret:
                    return rvec_init, tvec_init, n_extra, reproj_before, None
            
            # Ошибка после уточнения
            proj_after, _ = cv2.projectPoints(
                obj_pts_combined, rvec_ref, tvec_ref, camera_matrix, dist_coeffs
            )
            errors_after = np.linalg.norm(
                proj_after.reshape(-1, 2) - img_pts_combined.reshape(-1, 2), axis=1
            )
            reproj_after = float(np.mean(errors_after))
            median_after = float(np.median(errors_after))
            
            # Проверка качества
            if (reproj_after > reproj_before * 1.3 or
                median_after > median_before * 1.2 or
                reproj_after > 15.0):
                return rvec_init, tvec_init, n_extra, reproj_before, reproj_after
            
            return rvec_ref, tvec_ref, n_extra, reproj_before, reproj_after
            
        except Exception as e:
            print(f"Pose refinement error: {e}")
            return rvec_init, tvec_init, n_extra, reproj_before, None
