"""
Наложение информационного текста на кадр
"""
import cv2


class InfoOverlay:
    """Отрисовка информационного текста на кадре"""
    
    def __init__(self, config):
        self.config = config
        self.font_scale = config.get('font_scale', 0.7)
        self.font_thickness = config.get('font_thickness', 2)
        self.line_spacing = config.get('line_spacing', 40)
        self.target_id = 3  # значение по умолчанию
    
    def create_info_lines(self, fps, video_only, tag_info, params,
                         marker_detected, n_pyramid_found, refine_reproj_info):
        """Создание списка информационных строк"""
        
        info_lines = [
            f"FPS: {fps:.1f}  |  Mode: {'VIDEO ONLY' if video_only else 'NORMAL'}",
            f"Target ID: {self.target_id}",
            tag_info,
        ]
        
        if not video_only:
            info_lines.extend([
                f"Scale: {params['scale']:.6f}",
                f"Rot: {params['rot_x']:6.2f} {params['rot_y']:6.2f} "
                f"{params['rot_z']:6.2f} deg",
                f"Offset: X:{params['offset_x']:+.4f} Y:{params['offset_y']:+.4f} "
                f"Z:{params['offset_z']:+.4f}m",
            ])
        
        # Информация о пирамиде
        rb, ra = refine_reproj_info
        if rb is not None:
            if ra is not None:
                info_lines.append(
                    f"Lines: {n_pyramid_found}/4 pts | reproj {rb:.1f}->{ra:.1f}px"
                )
            else:
                info_lines.append(
                    f"Lines: {n_pyramid_found}/4 pts | reproj {rb:.1f}px (no refine)"
                )
        elif n_pyramid_found > 0:
            info_lines.append(f"Lines: {n_pyramid_found}/4 pts")
        
        return info_lines
    
    def draw_info(self, frame, info_lines):
        """Отрисовка информационных строк на кадре"""
        height = frame.shape[0]
        
        y_pos = height - len(info_lines) * int(self.line_spacing * self.font_scale) - 20
        
        for line in info_lines:
            cv2.putText(frame, line, (10, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX,
                       self.font_scale,
                       (255, 255, 255),
                       self.font_thickness)
            y_pos += int(self.line_spacing * self.font_scale)
        
        return frame