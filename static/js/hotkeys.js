function setupChannelHotkeys(getTabs) {
    document.addEventListener('keydown', (event) => {
        if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        if (document.querySelector('dialog[open]')) return;
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;

        const tabs = getTabs();
        if (tabs.length === 0) return;

        const selected = tabs.findIndex(tab => tab.checked);
        let next = null;
        if (event.key === 'ArrowLeft') {
            next = selected <= 0 ? tabs.length - 1 : selected - 1;
        } else if (event.key === 'ArrowRight') {
            next = selected === -1 || selected === tabs.length - 1 ? 0 : selected + 1;
        } else if (/^[1-9]$/.test(event.key)) {
            const index = Number(event.key) - 1;
            if (index < tabs.length) next = index;
        }

        if (next === null) return;
        event.preventDefault();
        tabs[next].click();
    });
}
