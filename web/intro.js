/*
  intro.js - GeoMine-AI logo opening animation for any web page.

  USE: put intro.js in the same folder as earth.html (http://localhost:8000/web/intro.js)
  and add ONE line just before </body> in earth.html:

      <script src="intro.js"></script>

  Settings (edit below):
    PLAY_ONCE_PER_TAB = false  -> plays on every page load (best while testing)
                         true   -> plays once per browser tab session
*/
(function () {
  var TITLE = "GeoMine-AI";
  var TAGLINE = "Real-time manganese production intelligence";
  var DURATION_MS = 5200;          // total time before the overlay is removed
  var PLAY_ONCE_PER_TAB = false;

  try {
    if (PLAY_ONCE_PER_TAB && sessionStorage.getItem("gm_intro_done")) return;
    sessionStorage.setItem("gm_intro_done", "1");
  } catch (e) {}

  var css = [
    "#gm-splash{position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:2147483647;",
    "display:flex;flex-direction:column;align-items:center;justify-content:center;",
    "background:radial-gradient(circle at 50% 40%,#1b2b3a 0%,#0b1118 70%);",
    "font-family:'Segoe UI',system-ui,sans-serif;animation:gmOut .9s ease 4.2s forwards}",
    "@keyframes gmOut{to{opacity:0;visibility:hidden}}",
    "#gm-splash .logo{width:150px;height:150px;animation:gmFloat 3s ease-in-out infinite}",
    "#gm-splash .hex{fill:none;stroke:#ffb300;stroke-width:3;stroke-dasharray:330;stroke-dashoffset:330;animation:gmDraw 1.4s ease forwards}",
    "#gm-splash .peak{fill:#ffb300;opacity:0;transform-box:fill-box;transform-origin:50% 100%;animation:gmRise .7s cubic-bezier(.2,.9,.3,1.2) forwards}",
    "#gm-splash .p1{animation-delay:1s}",
    "#gm-splash .p2{animation-delay:1.2s;fill:#ff7043}",
    "#gm-splash .node{fill:#4fc3f7;opacity:0;animation:gmPop .5s ease forwards}",
    "#gm-splash .line{stroke:#4fc3f7;stroke-width:1.5;opacity:0;animation:gmPop .5s ease forwards}",
    "#gm-splash .ring{fill:none;stroke:#ffb300;stroke-width:2;opacity:0;transform-box:fill-box;transform-origin:50% 50%;animation:gmRing 1.6s ease-out 1.5s forwards}",
    "@keyframes gmDraw{to{stroke-dashoffset:0}}",
    "@keyframes gmRise{from{opacity:0;transform:scaleY(0)}to{opacity:1;transform:scaleY(1)}}",
    "@keyframes gmPop{from{opacity:0}to{opacity:1}}",
    "@keyframes gmRing{0%{opacity:.8;transform:scale(.6)}100%{opacity:0;transform:scale(1.9)}}",
    "@keyframes gmFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}",
    "#gm-splash .title{margin-top:18px;font-size:44px;font-weight:700;letter-spacing:2px;color:#fff}",
    "#gm-splash .title span{display:inline-block;opacity:0;transform:translateY(18px);animation:gmLetter .5s ease forwards}",
    "#gm-splash .title span.acc{color:#4fc3f7}",
    "@keyframes gmLetter{to{opacity:1;transform:translateY(0)}}",
    "#gm-splash .tag{margin-top:8px;font-size:16px;color:#90a4ae;letter-spacing:1px;opacity:0;animation:gmPop .8s ease 2.9s forwards}",
    "#gm-splash .bar{margin-top:28px;width:220px;height:3px;background:#263238;border-radius:3px;overflow:hidden;opacity:0;animation:gmPop .4s ease 2.8s forwards}",
    "#gm-splash .bar div{height:100%;width:0;background:linear-gradient(90deg,#ffb300,#4fc3f7);animation:gmLoad 1.4s ease-in-out 2.9s forwards}",
    "@keyframes gmLoad{to{width:100%}}"
  ].join("");

  function letters() {
    var out = "";
    for (var i = 0; i < TITLE.length; i++) {
      var ch = TITLE.charAt(i) === " " ? "&nbsp;" : TITLE.charAt(i);
      out += '<span class="' + (i >= 8 ? "acc" : "") + '" style="animation-delay:' +
             (1.9 + i * 0.07).toFixed(2) + 's">' + ch + "</span>";
    }
    return out;
  }

  var body =
    '<svg class="logo" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">' +
    '<circle class="ring" cx="60" cy="60" r="50"/>' +
    '<polygon class="hex" points="60,6 106,33 106,87 60,114 14,87 14,33"/>' +
    '<polygon class="peak p1" points="30,88 52,48 74,88"/>' +
    '<polygon class="peak p2" points="52,88 76,40 100,88"/>' +
    '<line class="line" x1="38" y1="34" x2="60" y2="26" style="animation-delay:1.7s"/>' +
    '<line class="line" x1="60" y1="26" x2="84" y2="34" style="animation-delay:1.8s"/>' +
    '<circle class="node" cx="38" cy="34" r="3.5" style="animation-delay:1.6s"/>' +
    '<circle class="node" cx="60" cy="26" r="3.5" style="animation-delay:1.7s"/>' +
    '<circle class="node" cx="84" cy="34" r="3.5" style="animation-delay:1.8s"/>' +
    "</svg>" +
    '<div class="title">' + letters() + "</div>" +
    '<div class="tag">' + TAGLINE + "</div>" +
    '<div class="bar"><div></div></div>';

  function play() {
    var style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
    var o = document.createElement("div");
    o.id = "gm-splash";
    o.innerHTML = body;
    document.body.appendChild(o);
    setTimeout(function () { o.remove(); style.remove(); }, DURATION_MS);
  }

  if (document.body) play();
  else document.addEventListener("DOMContentLoaded", play);
})();
