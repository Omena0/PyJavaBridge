package com.pyjavabridge.facade;

import com.pyjavabridge.PyJavaBridgePlugin;
import com.pyjavabridge.BridgeInstance;

public class CommandsFacade {
    private final PyJavaBridgePlugin plugin;
    private final BridgeInstance instance;

    public CommandsFacade(PyJavaBridgePlugin plugin, BridgeInstance instance) {
        this.plugin = plugin;
        this.instance = instance;
    }

    public void register(String name) {
        plugin.registerScriptCommand(name, instance);
    }
}
