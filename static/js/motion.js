/* Deep Thought motion layer: reveal, parallax, smooth chat and micro-interactions. */
(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const doc = document.documentElement;

    const liftCurtain = () => {
        const curtain = document.getElementById("curtain");
        if (!curtain) return;
        curtain.classList.add("gone");
        window.setTimeout(() => curtain.remove(), 900);
    };

    const revealWorkspace = () => {
        document.querySelector(".headline[data-reveal]")?.classList.add("revealed");
        document.querySelectorAll(".subhead[data-reveal], .chapter").forEach((element) => {
            element.classList.add("in");
        });
    };

    window.addEventListener("load", () => {
        window.setTimeout(liftCurtain, prefersReduced ? 60 : 900);
        window.setTimeout(revealWorkspace, prefersReduced ? 0 : 350);
    });

    const chat = document.getElementById("chatWindow");
    if (chat && window.Lenis && !prefersReduced) {
        try {
            const lenis = new window.Lenis({
                wrapper: chat,
                content: document.getElementById("messages") || chat,
                duration: 1.05,
                easing: (time) => 1 - Math.pow(1 - time, 4),
                smoothWheel: true,
                wheelMultiplier: 1,
            });
            const frame = (time) => {
                lenis.raf(time);
                window.requestAnimationFrame(frame);
            };
            window.requestAnimationFrame(frame);
            window.deepThoughtScroll = lenis;
        } catch (_error) {
            // Native scrolling remains available when Lenis cannot initialize.
        }
    }

    if (!prefersReduced) {
        const orbs = document.querySelectorAll("[data-parallax]");
        if (orbs.length) {
            let mouseX = 0;
            let mouseY = 0;
            let targetX = 0;
            let targetY = 0;
            window.addEventListener("pointermove", (event) => {
                targetX = (event.clientX / window.innerWidth - 0.5) * 2;
                targetY = (event.clientY / window.innerHeight - 0.5) * 2;
            }, { passive: true });
            const animateOrbs = () => {
                mouseX += (targetX - mouseX) * 0.06;
                mouseY += (targetY - mouseY) * 0.06;
                orbs.forEach((element) => {
                    const depth = Number.parseFloat(element.dataset.parallax || "0.1");
                    element.style.transform = `translate3d(${mouseX * 40 * depth}px, ${mouseY * 40 * depth}px, 0)`;
                });
                window.requestAnimationFrame(animateOrbs);
            };
            window.requestAnimationFrame(animateOrbs);
        }
    }

    const heroTag = document.querySelector(".hero-tag");
    const sendButton = document.getElementById("sendBtn");
    sendButton?.addEventListener("mouseenter", () => {
        if (!heroTag || prefersReduced) return;
        heroTag.animate(
            [{ transform: "translateY(0)" }, { transform: "translateY(-3px)" }, { transform: "translateY(0)" }],
            { duration: 500, easing: "cubic-bezier(.22,1,.36,1)" },
        );
    });

    document.getElementById("themeToggle")?.addEventListener("click", () => {
        if (prefersReduced) return;
        doc.animate(
            [{ filter: "brightness(1)" }, { filter: "brightness(.86)" }, { filter: "brightness(1)" }],
            { duration: 260, easing: "ease-out" },
        );
    });

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) entry.target.classList.add("in");
            });
        }, { threshold: 0.15 });
        document.querySelectorAll(".chapter").forEach((element) => observer.observe(element));
    }
})();
