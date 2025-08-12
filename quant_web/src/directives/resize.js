export default {
    mounted(el, binding) {
        const callback = binding.value;

        if (typeof callback !== 'function') {
            throw new Error('Resize directive requires a function as value');
        }

        const observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                callback(entry.contentRect);
            }
        });

        observer.observe(el);
        el._resizeObserver = observer;
    },

    unmounted(el) {
        if (el._resizeObserver) {
            el._resizeObserver.disconnect();
            delete el._resizeObserver;
        }
    }
};