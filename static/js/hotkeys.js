function setupChannelHotkeys(getTabs, getChannel) {
    // controls can change without reloading chat
    let controls = {hotkeys: {}, macros: []};

    function chordFor(event) {
        // turn browser key events into our stored chord format
        const parts = [];
        if (event.ctrlKey) parts.push('Ctrl');
        if (event.altKey) parts.push('Alt');
        if (event.shiftKey) parts.push('Shift');
        let key = event.key;
        if (key.length === 1) key = key.toUpperCase();
        parts.push(key);
        return parts.join('+').toLowerCase();
    }

    function invokeMacro(macro) {
        // every macro still ends up in the normal send path
        const send = () => socket.emit('run_macro', {id: macro.id, channel: getChannel()}, result => {
            if (!result.ok) makeNotification((result.errors || ['Macro failed.']).join('\n'), 5000, 'error');
        });
        if (!macro.confirm) {
            send();
            return;
        }
        makeNotification(`Send macro "${macro.name}"?\n${macro.command}`, 0, 'warning', {
            persistent: true,
            actions: [
                {label: 'Send', className: 'btn btn-sm btn-error', onClick: send},
                {label: 'Cancel', className: 'btn btn-sm btn-ghost', onClick: () => {}}
            ]
        });
    }

    function renderMacroButtons() {
        const container = document.getElementById('macro-buttons');
        if (!container) return;
        container.replaceChildren();
        controls.macros.filter(macro => macro.button).forEach(macro => {
            const button = document.createElement('button');
            button.className = 'btn btn-sm btn-outline';
            button.textContent = macro.name;
            button.title = macro.command;
            button.addEventListener('click', () => invokeMacro(macro));
            container.appendChild(button);
        });
    }

    function setSettings(settings) {
        controls = settings.controls || controls;
        renderMacroButtons();
    }

    socket.on('settings_changed', setSettings);
    socket.on('macro_confirmation', macro => invokeMacro(macro));
    socket.emit('settings_get', result => { if (result && result.ok) setSettings(result.data); });

    document.addEventListener('keydown', event => {
        // typing takes priority over shortcuts. shocking, I know.
        if (event.metaKey || document.querySelector('dialog[open]')) return;
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
        const chord = chordFor(event);
        const macro = controls.macros.find(item => item.hotkey && item.hotkey.toLowerCase() === chord);
        if (macro) {
            event.preventDefault();
            invokeMacro(macro);
            return;
        }
        const action = Object.entries(controls.hotkeys).find(([, hotkey]) => hotkey && hotkey.toLowerCase() === chord)?.[0];
        if (!action) return;
        const tabs = getTabs();
        if (tabs.length === 0) return;
        const selected = tabs.findIndex(tab => tab.checked);
        let next = null;
        if (action === 'previous_tab') next = selected <= 0 ? tabs.length - 1 : selected - 1;
        else if (action === 'next_tab') next = selected === -1 || selected === tabs.length - 1 ? 0 : selected + 1;
        else if (/^tab_[1-9]$/.test(action)) next = Number(action.slice(4)) - 1;
        if (next === null || next >= tabs.length) return;
        event.preventDefault();
        tabs[next].click();
    });
}
