"""
Slide templates for generating professional HTML/CSS presentations
"""
import json

SLIDE_TEMPLATES = {
    "modern": """
        <div class="slide {slide_class}" style="
            display: none;
            width: 100vw;
            height: 100vh;
            padding: 80px;
            box-sizing: border-box;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            position: relative;
            overflow: hidden;
        ">
            {content}
        </div>
    """,
    
    "minimal": """
        <div class="slide {slide_class}" style="
            display: none;
            width: 100vw;
            height: 100vh;
            padding: 80px;
            box-sizing: border-box;
            background: #ffffff;
            color: #1a1a1a;
            flex-direction: column;
            justify-content: center;
            align-items: flex-start;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            border-left: 8px solid #667eea;
        ">
            {content}
        </div>
    """,
    
    "dark": """
        <div class="slide {slide_class}" style="
            display: none;
            width: 100vw;
            height: 100vh;
            padding: 80px;
            box-sizing: border-box;
            background: #0a0a0a;
            color: #ffffff;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            position: relative;
        ">
            {content}
        </div>
    """,
    
    "corporate": """
        <div class="slide {slide_class}" style="
            display: none;
            width: 100vw;
            height: 100vh;
            padding: 80px;
            box-sizing: border-box;
            background: #f8f9fa;
            color: #212529;
            flex-direction: column;
            justify-content: flex-start;
            align-items: flex-start;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            border-top: 6px solid #0066cc;
        ">
            {content}
        </div>
    """,
    
    "creative": """
        <div class="slide {slide_class}" style="
            display: none;
            width: 100vw;
            height: 100vh;
            padding: 80px;
            box-sizing: border-box;
            background: linear-gradient(45deg, #ff6b6b 0%, #4ecdc4 100%);
            color: white;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            position: relative;
        ">
            {content}
        </div>
    """
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            overflow: hidden;
            width: 100vw;
            height: 100vh;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            margin: 0;
            padding: 0;
            overflow: hidden;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #000;
        }}
        
        .slide {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
        }}
        
        .slide.active {{
            display: flex !important;
        }}
        
        .slide-indicator {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 12px 24px;
            border-radius: 24px;
            font-size: 16px;
            font-weight: 600;
            z-index: 1000;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }}
        
        .slide-controls {{
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 12px;
            z-index: 1000;
        }}
        
        .slide-control-btn {{
            background: rgba(0, 0, 0, 0.7);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 24px;
            font-size: 14px;
            cursor: pointer;
            backdrop-filter: blur(10px);
            transition: all 0.2s;
        }}
        
        .slide-control-btn:hover {{
            background: rgba(0, 0, 0, 0.9);
            transform: scale(1.05);
        }}
        
        @media (max-width: 768px) {{
            .slide-controls {{
                flex-direction: column;
                gap: 8px;
            }}
            
            .slide-indicator {{
                bottom: 20px;
                right: 20px;
                font-size: 14px;
                padding: 10px 16px;
            }}
        }}
        
        .slide-title {{
            font-size: clamp(48px, 6vw, 80px);
            font-weight: 900;
            margin-bottom: 40px;
            line-height: 1.1;
            text-align: center;
            letter-spacing: -0.02em;
        }}
        
        .slide-subtitle {{
            font-size: clamp(28px, 3.5vw, 48px);
            font-weight: 700;
            margin-bottom: 30px;
            opacity: 0.95;
            letter-spacing: -0.01em;
        }}
        
        .slide-content {{
            font-size: clamp(20px, 2.5vw, 32px);
            line-height: 1.7;
            max-width: 1400px;
            text-align: center;
            font-weight: 400;
        }}
        
        .slide-list {{
            font-size: clamp(24px, 3vw, 40px);
            line-height: 2.2;
            list-style: none;
            text-align: left;
            max-width: 1200px;
        }}
        
        .slide-list li {{
            margin-bottom: 24px;
            padding-left: 50px;
            position: relative;
            font-weight: 500;
        }}
        
        .slide-list li:before {{
            content: '▸';
            position: absolute;
            left: 0;
            color: currentColor;
            font-size: 1.2em;
            font-weight: bold;
        }}
        
        .slide-image-placeholder {{
            width: min(800px, 60vw);
            height: min(500px, 40vh);
            background: rgba(255, 255, 255, 0.15);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 40px auto;
            font-size: clamp(16px, 2vw, 24px);
            opacity: 0.7;
            border: 2px dashed rgba(255, 255, 255, 0.3);
        }}
        
        .slide-stat {{
            display: inline-block;
            padding: 40px 60px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 20px;
            margin: 20px;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s;
        }}
        
        .slide-stat:hover {{
            transform: scale(1.05);
        }}
        
        .slide-stat-value {{
            font-size: clamp(56px, 7vw, 96px);
            font-weight: 900;
            display: block;
            margin-bottom: 12px;
            letter-spacing: -0.03em;
        }}
        
        .slide-stat-label {{
            font-size: clamp(18px, 2vw, 28px);
            opacity: 0.95;
            font-weight: 600;
        }}
        
        .slide-section {{
            width: 100%;
            max-width: 1400px;
        }}
        
        .slide-header {{
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 20px;
            opacity: 0.8;
        }}
        
        .chart-container {{
            width: 100%;
            max-width: 800px;
            height: 400px;
            margin: 30px auto;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }}
        
        .chart-wrapper {{
            position: relative;
            width: 100%;
            height: 100%;
        }}
    </style>
</head>
<body>
    {slides}
    <div class="slide-indicator">1 / {slide_count}</div>
    <div class="slide-controls">
        <button class="slide-control-btn" onclick="previousSlide()">← Previous</button>
        <button class="slide-control-btn" onclick="nextSlide()">Next →</button>
    </div>
</body>
</html>
"""

def create_slide_content(slide_data: dict, template_style: str = "modern") -> str:
    """Create slide content based on slide data"""
    slide_type = slide_data.get("type", "title")
    title = slide_data.get("title", "")
    content = slide_data.get("content", "")
    
    if slide_type == "title":
        return f"""
            <div class="slide-section">
                <h1 class="slide-title">{title}</h1>
                {f'<p class="slide-content" style="font-size: 32px; opacity: 0.9;">{content}</p>' if content else ''}
            </div>
        """
    elif slide_type == "content":
        return f"""
            <div class="slide-section">
                {f'<h2 class="slide-subtitle">{title}</h2>' if title else ''}
                <div class="slide-content">{content}</div>
            </div>
        """
    elif slide_type == "list":
        items = slide_data.get("items", [])
        items_html = "\n".join([f"<li>{item}</li>" for item in items])
        return f"""
            <div class="slide-section">
                {f'<h2 class="slide-subtitle">{title}</h2>' if title else ''}
                <ul class="slide-list">{items_html}</ul>
            </div>
        """
    elif slide_type == "stats":
        stats = slide_data.get("stats", [])
        stats_html = "\n".join([
            f'<div class="slide-stat"><span class="slide-stat-value">{stat.get("value", "")}</span><span class="slide-stat-label">{stat.get("label", "")}</span></div>'
            for stat in stats
        ])
        return f"""
            <div class="slide-section">
                {f'<h2 class="slide-subtitle">{title}</h2>' if title else ''}
                <div style="display: flex; flex-wrap: wrap; justify-content: center; align-items: center;">
                    {stats_html}
                </div>
            </div>
        """
    elif slide_type == "image":
        return f"""
            <div class="slide-section">
                {f'<h2 class="slide-subtitle">{title}</h2>' if title else ''}
                <div class="slide-image-placeholder">
                    {content or '[Image Placeholder]'}
                </div>
            </div>
        """
    elif slide_type == "chart":
        chart_data = slide_data.get("chart_data", {})
        chart_type = chart_data.get("type", "bar")  # bar, line, pie, doughnut
        chart_hash = abs(hash(str(slide_data))) % 10000
        chart_id = f"chart_{chart_hash}"
        
        labels = chart_data.get("labels", [])
        datasets = chart_data.get("datasets", [])
        
        # Determine text color based on template
        is_dark_theme = template_style in ["dark", "modern", "creative"]
        text_color = "#ffffff" if is_dark_theme else "#1a1a1a"
        grid_color = "rgba(255, 255, 255, 0.1)" if is_dark_theme else "rgba(0, 0, 0, 0.1)"
        
        # Build options
        options = {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {
                    "display": True,
                    "position": "top",
                    "labels": {
                        "color": text_color,
                        "font": {"size": 14}
                    }
                },
                "title": {
                    "display": bool(title),
                    "text": title,
                    "color": text_color,
                    "font": {"size": 18, "weight": "bold"}
                }
            }
        }
        
        # Add scales for bar and line charts
        if chart_type in ["bar", "line"]:
            options["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "ticks": {"color": text_color},
                    "grid": {"color": grid_color}
                },
                "x": {
                    "ticks": {"color": text_color},
                    "grid": {"color": grid_color}
                }
            }
        
        chart_config = json.dumps({
            "type": chart_type,
            "data": {
                "labels": labels,
                "datasets": datasets
            },
            "options": options
        })
        
        return f"""
            <div class="slide-section">
                {f'<h2 class="slide-subtitle">{title}</h2>' if title else ''}
                <div class="chart-container">
                    <div class="chart-wrapper">
                        <canvas id="{chart_id}"></canvas>
                    </div>
                </div>
                <script type="application/json" data-chart-id="{chart_id}">{chart_config}</script>
            </div>
        """
    else:
        return f"""
            <div class="slide-section">
                {f'<h2 class="slide-subtitle">{title}</h2>' if title else ''}
                <div class="slide-content">{content}</div>
            </div>
        """

