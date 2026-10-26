WOKWI_EMBED_URL = "https://wokwi.com/projects/478875514435866625?embed=1"


def build_wokwi_embed_html() -> str:
    return f"""
    <style>
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; background: #101923; color: #d9e6f2; font: 11px system-ui, sans-serif; }}
      #simulation-frame {{
        height: min(760px, calc(100vh - 120px));
        width: 100%;
        min-height: 400px;
        max-height: calc(100vh - 80px);
        max-width: 100%;
        resize: both;
        overflow: auto;
        border: 1px solid rgba(125,175,210,.35);
        border-radius: 10px;
        background: #101923;
      }}
      #simulation-tools {{
        height: 38px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 10px;
      }}
      #simulation-tools button {{
        color: #e8f2fb;
        background: #23455f;
        border: 1px solid #507895;
        border-radius: 6px;
        padding: 4px 8px;
        font: inherit;
        cursor: pointer;
      }}
      #wokwi-project {{ display: block; width: 100%; height: calc(100% - 38px); border: 0; }}
      #simulation-frame:fullscreen {{ width: 100vw; height: 100vh; max-height: 100vh; resize: none; }}
      #simulation-frame:fullscreen #wokwi-project {{ height: calc(100% - 38px); }}
    </style>
    <div id="simulation-frame">
      <div id="simulation-tools">
        <span>Drag the lower-right corner to resize width and height</span>
        <button id="fullscreen-simulation" type="button">Enlarge</button>
      </div>
      <iframe
        id="wokwi-project"
        src="{WOKWI_EMBED_URL}"
        title="Interactive Wokwi diesel tank simulation"
        allow="fullscreen; clipboard-read; clipboard-write"
        allowfullscreen
      ></iframe>
    </div>
    <script>
      document.getElementById("fullscreen-simulation").addEventListener("click", () => {{
        const frame = document.getElementById("simulation-frame");
        if (document.fullscreenElement) {{
          document.exitFullscreen();
        }} else if (frame.requestFullscreen) {{
          frame.requestFullscreen();
        }}
      }});
    </script>
    """
