import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import App from "@/App.vue";

describe("Smoke", () => {
  it("mounts App without crash", () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: "/",
          component: { template: "<div/>" },
        },
      ],
    });

    expect(() =>
      mount(App, {
        global: {
          plugins: [router],
          stubs: {
            RouterView: { template: "<div/>" },
          },
        },
      }),
    ).not.toThrow();
  });
});
