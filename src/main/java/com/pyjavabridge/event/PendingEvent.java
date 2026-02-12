package com.pyjavabridge.event;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;
import org.bukkit.block.Block;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;

public class PendingEvent {
    public final CountDownLatch latch = new CountDownLatch(1);
    public final AtomicBoolean cancelRequested = new AtomicBoolean(false);
    public Cancellable cancellable;
    public Block block;
    public Event event;
    public int id;
    public String chatOverride;
    public Double damageOverride;
}
