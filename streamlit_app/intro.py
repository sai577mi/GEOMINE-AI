"""
intro.py - animated logo opening for GeoMine-AI (plays once per session).

Use in app.py, right after st.set_page_config(...):

    import intro
    intro.show_intro()

The animation plays in its own frame at the top of the page for about 5 seconds,
then the frame is removed and the app appears. It does not touch the browser page
from outside, so it works on any Streamlit version that has components.html.
"""

import time

import streamlit as st
import streamlit.components.v1 as components

TITLE = "GeoMine-AI"
TAGLINE = "Real-time manganese production intelligence"
DURATION = 5.0  # seconds the intro stays on screen


def _letters(text, start=1.6, step=0.07):
    out = []
    for i, ch in enumerate(text):
        shown = "&nbsp;" if ch == " " else ch
        cls = ' class="acc"' if i >= 8 else ""
        out.append(f'<span{cls} style="animation-delay:{start + i * step:.2f}s">{shown}</span>')
    return "".join(out)


PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
html, body { margin: 0; height: 100%; background: transparent; }
.splash {
  height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: radial-gradient(circle at 50% 40%, #1b2b3a 0%, #0b1118 70%);
  border-radius: 12px; font-family: "Segoe UI", system-ui, sans-serif; overflow: hidden;
  animation: out 0.6s ease __FADE__s forwards;
}
@keyframes out { to { opacity: 0; } }
.logo { width: 140px; height: 140px; animation: float 3s ease-in-out infinite; }
.hex { fill: none; stroke: #ffb300; stroke-width: 3; stroke-dasharray: 330; stroke-dashoffset: 330;
  animation: draw 1.3s ease forwards; }
.peak { fill: #ffb300; opacity: 0; transform-box: fill-box; transform-origin: 50% 100%;
  animation: rise 0.7s cubic-bezier(.2,.9,.3,1.2) forwards; }
.p1 { animation-delay: 0.9s; }
.p2 { animation-delay: 1.1s; fill: #ff7043; }
.node { fill: #4fc3f7; opacity: 0; animation: pop 0.5s ease forwards; }
.line { stroke: #4fc3f7; stroke-width: 1.5; opacity: 0; animation: pop 0.5s ease forwards; }
.ring { fill: none; stroke: #ffb300; stroke-width: 2; opacity: 0; transform-box: fill-box;
  transform-origin: 50% 50%; animation: ring 1.6s ease-out 1.3s forwards; }
@keyframes draw { to { stroke-dashoffset: 0; } }
@keyframes rise { from { opacity: 0; transform: scaleY(0); } to { opacity: 1; transform: scaleY(1); } }
@keyframes pop { from { opacity: 0; } to { opacity: 1; } }
@keyframes ring { 0% { opacity: .8; transform: scale(.6); } 100% { opacity: 0; transform: scale(1.9); } }
@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
.title { margin-top: 14px; font-size: 42px; font-weight: 700; letter-spacing: 2px; color: #fff; }
.title span { display: inline-block; opacity: 0; transform: translateY(16px); animation: letter 0.5s ease forwards; }
.title span.acc { color: #4fc3f7; }
@keyframes letter { to { opacity: 1; transform: translateY(0); } }
.tag { margin-top: 6px; font-size: 15px; color: #90a4ae; letter-spacing: 1px; opacity: 0;
  animation: pop 0.8s ease 2.6s forwards; }
.bar { margin-top: 22px; width: 220px; height: 3px; background: #263238; border-radius: 3px; overflow: hidden;
  opacity: 0; animation: pop 0.4s ease 2.5s forwards; }
.bar div { height: 100%; width: 0; background: linear-gradient(90deg, #ffb300, #4fc3f7);
  animation: load 1.6s ease-in-out 2.6s forwards; }
@keyframes load { to { width: 100%; } }
</style></head>
<body>
<div class="splash">
  <svg class="logo" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
    <circle class="ring" cx="60" cy="60" r="50"/>
    <polygon class="hex" points="60,6 106,33 106,87 60,114 14,87 14,33"/>
    <polygon class="peak p1" points="30,88 52,48 74,88"/>
    <polygon class="peak p2" points="52,88 76,40 100,88"/>
    <line class="line" x1="38" y1="34" x2="60" y2="26" style="animation-delay:1.5s"/>
    <line class="line" x1="60" y1="26" x2="84" y2="34" style="animation-delay:1.6s"/>
    <circle class="node" cx="38" cy="34" r="3.5" style="animation-delay:1.4s"/>
    <circle class="node" cx="60" cy="26" r="3.5" style="animation-delay:1.5s"/>
    <circle class="node" cx="84" cy="34" r="3.5" style="animation-delay:1.6s"/>
  </svg>
  <div class="title">__LETTERS__</div>
  <div class="tag">__TAGLINE__</div>
  <div class="bar"><div></div></div>
</div>
</body></html>
"""


def show_intro(force=False):
    if st.session_state.get("intro_done") and not force:
        return
    st.session_state.intro_done = True

    page = (PAGE.replace("__LETTERS__", _letters(TITLE))
                .replace("__TAGLINE__", TAGLINE)
                .replace("__FADE__", f"{DURATION - 0.8:.1f}"))
    slot = st.empty()
    with slot.container():
        components.html(page, height=420)
    time.sleep(DURATION)
    slot.empty()