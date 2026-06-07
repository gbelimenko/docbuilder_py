import os
import logging

logger = logging.getLogger("DocBuilder.Themes")

def hex_to_rgb(hex_str: str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = "".join(c*2 for c in hex_str)
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def clamp(val, min_val=0, max_val=255):
    return max(min_val, min(val, max_val))

def adjust_lightness(hex_str: str, factor: float) -> str:
    try:
        r, g, b = hex_to_rgb(hex_str)
        r = clamp(int(r * factor))
        g = clamp(int(g * factor))
        b = clamp(int(b * factor))
        return rgb_to_hex((r, g, b))
    except Exception as e:
        logger.error(f"Error adjusting lightness for {hex_str}: {e}")
        return hex_str

def get_soft_blend(hex_str: str, bg_hex: str, ratio: float = 0.12) -> str:
    try:
        r1, g1, b1 = hex_to_rgb(hex_str)
        r2, g2, b2 = hex_to_rgb(bg_hex)
        r = clamp(int(r1 * ratio + r2 * (1 - ratio)))
        g = clamp(int(g1 * ratio + g2 * (1 - ratio)))
        b = clamp(int(b1 * ratio + b2 * (1 - ratio)))
        return rgb_to_hex((r, g, b))
    except Exception as e:
        logger.error(f"Error blending colors {hex_str} and {bg_hex}: {e}")
        return hex_str

def buildTheme(mode: str = "dark", accent: str = "#3B82F6") -> dict:
    mode = mode.lower() if mode else "dark"
    if mode not in ["light", "dark"]:
        mode = "dark"
        
    accent = accent or "#3B82F6"
    
    if mode == "light":
        bg = "#F6F7F9"
        surface = "#FFFFFF"
        surface2 = "#F1F3F5"
        border = "#DDE1E6"
        text = "#1F2933"
        text_sec = "#64748B"
        text_mut = "#94A3B8"
        log_bg = "#0B1020"
        log_text = "#D1D5DB"
        
        primary = accent
        primary_hover = adjust_lightness(accent, 0.88)
        primary_pressed = adjust_lightness(accent, 0.78)
        primary_soft = get_soft_blend(accent, bg, 0.12)
    else:
        bg = "#111214"
        surface = "#181A1F"
        surface2 = "#20232A"
        border = "#2E333D"
        text = "#F8FAFC"
        text_sec = "#CBD5E1"
        text_mut = "#94A3B8"
        log_bg = "#050816"
        log_text = "#D1D5DB"
        
        primary = accent
        primary_hover = adjust_lightness(accent, 1.12)
        primary_pressed = adjust_lightness(accent, 1.25)
        primary_soft = get_soft_blend(accent, bg, 0.15)
        
    return {
        "mode": mode,
        "accent": accent,
        "colors": {
            "bg": bg,
            "surface": surface,
            "surface2": surface2,
            "border": border,
            "text": text,
            "textSecondary": text_sec,
            "textMuted": text_mut,
            "primary": primary,
            "primaryHover": primary_hover,
            "primaryPressed": primary_pressed,
            "primarySoft": primary_soft,
            "success": "#10B981",
            "warning": "#F59E0B",
            "danger": "#EF4444",
            "info": "#3B82F6",
            "logBg": log_bg,
            "logText": log_text
        }
    }
