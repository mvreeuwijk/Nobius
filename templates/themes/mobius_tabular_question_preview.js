document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".tabs-container").forEach((tabsContainer) => {
    const tabs = Array.from(tabsContainer.querySelectorAll(".tab"));
    const partsContainer = tabsContainer.nextElementSibling;
    if (!partsContainer || !partsContainer.classList.contains("parts-container")) {
      return;
    }
    const parts = Array.from(partsContainer.querySelectorAll(".part"));
    const activate = (index) => {
      tabs.forEach((tab, tabIndex) => tab.classList.toggle("active", tabIndex === index));
      parts.forEach((part, partIndex) => part.classList.toggle("active", partIndex === index));
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(index));
    });
    activate(Math.max(0, tabs.findIndex((tab) => tab.classList.contains("active"))));
  });

  document.querySelectorAll(".check-help-button").forEach((button) => {
    button.addEventListener("click", () => {
      const match = button.id.match(/\d+/);
      if (!match) {
        return;
      }
      const part = document.querySelector(`#part${match[0]}`);
      if (!part) {
        return;
      }
      part.querySelector(".answers-container")?.classList.toggle("active");
      part.querySelector(".answers-nav-container")?.classList.toggle("active");
    });
  });

  const bindPanelButton = (buttonSelector, panelSelector, warningSelector, extraOnOpen) => {
    document.querySelectorAll(buttonSelector).forEach((button) => {
      button.addEventListener("click", () => {
        const match = button.id.match(/\d+/);
        if (!match) {
          return;
        }
        const part = document.querySelector(`#part${match[0]}`);
        if (!part) {
          return;
        }
        if (!button.classList.contains("open")) {
          part.querySelector(".answers-container > .active")?.classList.remove("active");
          part.querySelector(".answers-nav-container > .open")?.classList.remove("open");
          if (warningSelector) {
            part.querySelector(warningSelector)?.classList.remove("active");
          }
        }
        part.querySelector(panelSelector)?.classList.toggle("active");
        button.classList.toggle("open");
        if (typeof extraOnOpen === "function") {
          extraOnOpen(button, part);
        }
      });

      if (warningSelector) {
        button.addEventListener("mouseenter", () => {
          if (!button.classList.contains("open")) {
            const match = button.id.match(/\d+/);
            if (!match) {
              return;
            }
            document.querySelector(`#part${match[0]} ${warningSelector}`)?.classList.add("active");
          }
        });
        button.addEventListener("mouseleave", () => {
          if (!button.classList.contains("open")) {
            const match = button.id.match(/\d+/);
            if (!match) {
              return;
            }
            document.querySelector(`#part${match[0]} ${warningSelector}`)?.classList.remove("active");
          }
        });
      }
    });
  };

  bindPanelButton(".equation-help-button", ".equation-help", null);
  bindPanelButton(".final-answer-button", ".final-answer", ".awt-show-answer");
  bindPanelButton(".worked-solutions-button", ".worked-solutions", ".awt-worked-solutions");
  bindPanelButton(
    ".structured-tutorial-button",
    ".structured-tutorial",
    ".awt-structured-tutorial",
    () => window.dispatchEvent(new Event("resize"))
  );

  document.querySelectorAll(".sbs-step-down").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.classList.contains("disabled")) {
        return;
      }
      const navContainer = button.parentElement;
      if (!navContainer) {
        return;
      }
      const nextEl = navContainer.nextElementSibling;
      if (!nextEl || !nextEl.classList.contains("sbs-step")) {
        return;
      }
      nextEl.classList.toggle("active");
      navContainer.parentNode.insertBefore(nextEl, navContainer);
      if (nextEl.classList.contains("last")) {
        button.classList.add("disabled");
        navContainer.querySelector(".sbs-reveal-all")?.classList.add("disabled");
      }
      navContainer.querySelector(".sbs-step-up")?.classList.remove("disabled");
    });
  });

  document.querySelectorAll(".sbs-step-up").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.classList.contains("disabled")) {
        return;
      }
      const navContainer = button.parentElement;
      if (!navContainer) {
        return;
      }
      const prevEl = navContainer.previousElementSibling;
      if (!prevEl || !prevEl.classList.contains("sbs-step")) {
        return;
      }
      prevEl.classList.toggle("active");
      navContainer.insertAdjacentElement("afterend", prevEl);
      if (prevEl.classList.contains("second")) {
        button.classList.add("disabled");
      }
      navContainer.querySelector(".sbs-step-down")?.classList.remove("disabled");
      navContainer.querySelector(".sbs-reveal-all")?.classList.remove("disabled");
    });
  });

  document.querySelectorAll(".sbs-reveal-all").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.classList.contains("disabled")) {
        return;
      }
      const navContainer = button.parentElement;
      const parent = navContainer?.parentElement;
      const lastStep = parent?.querySelector(".last");
      if (!navContainer || !parent || !lastStep) {
        return;
      }
      lastStep.insertAdjacentElement("afterend", navContainer);
      parent.querySelectorAll(".sbs-step").forEach((step) => step.classList.add("active"));
      navContainer.querySelector(".sbs-step-up")?.classList.remove("disabled");
      navContainer.querySelector(".sbs-step-down")?.classList.add("disabled");
      button.classList.add("disabled");
    });
  });
});
