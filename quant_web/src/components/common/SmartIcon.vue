<!-- 智能图标组件 - 统一图标管理 -->
<template>
  <n-icon v-bind="$attrs" :component="getIconComponent" />
</template>

<script>
import { defineComponent, computed } from "vue";
import { NIcon } from "naive-ui";
import { icons } from "@/utils/icons";

export default defineComponent({
  name: "SmartIcon",
  components: { NIcon },
  props: {
    name: {
      type: String,
      required: true,
      validator: (value) => Object.keys(icons).includes(value),
    },
  },
  setup(props) {
    const getIconComponent = computed(() => {
      return icons[props.name];
    });

    return {
      getIconComponent,
    };
  },
});
</script>
