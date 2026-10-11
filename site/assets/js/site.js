/* smelt site — motion and components
 * GSAP 3.13 (No Charge license). Vendored — no CDN.
 * Respects prefers-reduced-motion. Page is usable with JS disabled.
 */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.documentElement.classList.add("js");

  if (typeof gsap === "undefined") return;
  gsap.registerPlugin(ScrollTrigger);
  if (typeof SplitText !== "undefined") gsap.registerPlugin(SplitText);
  if (typeof DrawSVGPlugin !== "undefined") gsap.registerPlugin(DrawSVGPlugin);
  if (typeof MotionPathPlugin !== "undefined") gsap.registerPlugin(MotionPathPlugin);

  /* ---------- Ember particles (hero only, capped) ---------- */
  function initEmbers() {
    var canvas = document.getElementById("embers");
    if (!canvas || reduceMotion) return;
    var ctx = canvas.getContext("2d");
    var W, H, particles = [];
    var CAP = 30;

    function resize() {
      var hero = canvas.parentElement;
      W = canvas.width = hero.offsetWidth;
      H = canvas.height = hero.offsetHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    function spawn() {
      return {
        x: Math.random() * W,
        y: H + 10,
        r: Math.random() * 1.8 + 0.6,
        vy: -(Math.random() * 0.4 + 0.15),
        vx: (Math.random() - 0.5) * 0.3,
        life: 1,
        decay: Math.random() * 0.004 + 0.002,
      };
    }
    for (var i = 0; i < CAP; i++) {
      var p = spawn();
      p.y = Math.random() * H;
      particles.push(p);
    }

    var running = true;
    // Pause when hero off-screen
    var io = new IntersectionObserver(function (entries) {
      running = entries[0].isIntersecting;
      if (running) requestAnimationFrame(tick);
    }, { threshold: 0 });
    io.observe(canvas);

    function tick() {
      if (!running) return;
      ctx.clearRect(0, 0, W, H);
      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life -= p.decay;
        if (p.life <= 0 || p.y < -10) {
          particles[i] = spawn();
          continue;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle =
          "rgba(255, 109, 58," + (p.life * 0.6).toFixed(3) + ")";
        ctx.fill();
      }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ---------- Hero heat-up ---------- */
  function initHero() {
    var h1 = document.querySelector(".hero h1");
    if (!h1) return;
    if (reduceMotion) return;
    var words = h1.querySelectorAll(".word");
    gsap.from(words, {
      y: 40,
      opacity: 0,
      duration: 0.8,
      stagger: 0.08,
      ease: "power3.out",
    });
    gsap.from(".hero .hero-sub, .hero .hero-actions", {
      y: 20,
      opacity: 0,
      duration: 0.7,
      delay: 0.4,
      stagger: 0.1,
      ease: "power3.out",
    });
  }

  /* ---------- Terminal typing replay ---------- */
  function initTerminal() {
    var term = document.getElementById("demo-terminal");
    if (!term) return;
    var lines = JSON.parse(term.getAttribute("data-lines") || "[]");
    var body = term.querySelector(".terminal-body");
    if (!body) return;

    if (reduceMotion) {
      // Static: show all lines immediately
      lines.forEach(function (l) { body.innerHTML += renderLine(l) + "\n"; });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      if (!entries[0].isIntersecting) return;
      io.disconnect();
      var idx = 0;
      function next() {
        if (idx >= lines.length) {
          body.classList.add("done");
          return;
        }
        var l = lines[idx++];
        body.innerHTML += renderLine(l) + "\n";
        body.scrollTop = body.scrollHeight;
        setTimeout(next, l[1] || 400);
      }
      setTimeout(next, 600);
    }, { threshold: 0.3 });
    io.observe(term);
  }

  function renderLine(l) {
    // l = [class, text, delayMs]
    var cls = l[0] ? ' class="' + l[0] + '"' : "";
    return "<span" + cls + ">" + escapeHtml(l[1]) + "</span>";
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /* ---------- Scroll-driven loop diagram ---------- */
  function initLoop() {
    var steps = document.querySelectorAll(".loop-step");
    if (!steps.length) return;
    if (reduceMotion) {
      steps.forEach(function (s) { s.classList.add("active"); });
      return;
    }
    steps.forEach(function (step, i) {
      ScrollTrigger.create({
        trigger: step,
        start: "top 75%",
        onEnter: function () {
          gsap.to(step, {
            color: "#FF6D3A",
            duration: 0.4,
            ease: "power2.out",
          });
          step.classList.add("active");
        },
      });
    });
  }

  /* ---------- Number counters ---------- */
  function initCounters() {
    var els = document.querySelectorAll("[data-count]");
    if (!els.length) return;
    els.forEach(function (el) {
      var target = parseFloat(el.getAttribute("data-count"));
      if (reduceMotion) {
        el.textContent = fmt(target);
        return;
      }
      ScrollTrigger.create({
        trigger: el,
        start: "top 85%",
        once: true,
        onEnter: function () {
          var obj = { v: 0 };
          gsap.to(obj, {
            v: target,
            duration: 1.2,
            ease: "power2.out",
            onUpdate: function () { el.textContent = fmt(obj.v); },
          });
        },
      });
    });
    function fmt(v) {
      return Number.isInteger(v) ? String(v) : v.toFixed(2);
    }
  }

  /* ---------- Speedup bars ---------- */
  function initBars() {
    var bars = document.querySelectorAll(".speedup-bar-fill");
    if (!bars.length) return;
    if (reduceMotion) {
      bars.forEach(function (b) {
        b.style.width = b.getAttribute("data-w") + "%";
      });
      return;
    }
    bars.forEach(function (b) {
      var w = b.getAttribute("data-w");
      gsap.fromTo(b,
        { width: "0%" },
        {
          width: w + "%",
          duration: 1,
          ease: "power3.out",
          scrollTrigger: { trigger: b, start: "top 90%", once: true },
        }
      );
    });
  }

  /* ---------- SVG pipeline path draw ---------- */
  function initPipeline() {
    var path = document.querySelector(".pipeline-path");
    if (!path || typeof DrawSVGPlugin === "undefined") return;
    if (reduceMotion) {
      gsap.set(path, { drawSVG: "100%" });
      return;
    }
    gsap.fromTo(path,
      { drawSVG: "0%" },
      {
        drawSVG: "100%",
        duration: 2,
        ease: "power2.inOut",
        scrollTrigger: { trigger: path, start: "top 80%", once: true },
      }
    );
  }

  /* ---------- Copy to clipboard ---------- */
  function initCopy() {
    document.querySelectorAll("[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var text = btn.getAttribute("data-copy");
        navigator.clipboard.writeText(text).then(function () {
          var orig = btn.textContent;
          btn.textContent = "copied";
          setTimeout(function () { btn.textContent = orig; }, 1500);
        });
      });
    });
  }

  /* ---------- Docs search (client-side) ---------- */
  function initSearch() {
    var input = document.getElementById("docs-search");
    if (!input) return;
    var items = document.querySelectorAll(".doc-item");
    input.addEventListener("input", function () {
      var q = input.value.toLowerCase();
      items.forEach(function (it) {
        var t = it.textContent.toLowerCase();
        it.style.display = t.indexOf(q) === -1 ? "none" : "";
      });
    });
  }

  /* ---------- Init ---------- */
  function init() {
    initEmbers();
    initHero();
    initTerminal();
    initLoop();
    initCounters();
    initBars();
    initPipeline();
    initCopy();
    initSearch();
    ScrollTrigger.refresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
