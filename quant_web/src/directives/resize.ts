import { DirectiveBinding, ObjectDirective } from "vue";

interface ResizeDirectiveBinding extends DirectiveBinding {
  value: (rect: DOMRectReadOnly) => void;
}

export default {
  mounted(el: HTMLElement, binding: ResizeDirectiveBinding) {
    const callback = binding.value;

    if (typeof callback !== "function") {
      throw new Error("Resize directive requires a function as value");
    }

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        callback(entry.contentRect);
      }
    });

    observer.observe(el);
    (el as any)._resizeObserver = observer;
  },

  unmounted(el: HTMLElement) {
    if ((el as any)._resizeObserver) {
      (el as any)._resizeObserver.disconnect();
      delete (el as any)._resizeObserver;
    }
  },
} as ObjectDirective;
