package com.pyjavabridge.facade;

import org.bukkit.Bukkit;
import net.kyori.adventure.text.Component;

public class ChatFacade {
    public void broadcast(String message) {
        Bukkit.getServer().broadcast(Component.text(message));
    }
}
