package com.pyjavabridge.facade;

import com.pyjavabridge.PyJavaBridgePlugin;

import org.bukkit.Bukkit;

public class MetricsFacade {
    private final PyJavaBridgePlugin plugin;

    public MetricsFacade(PyJavaBridgePlugin plugin) {
        this.plugin = plugin;
    }

    public java.util.List<Double> tps() {
        double[] values = Bukkit.getServer().getTPS();
        java.util.List<Double> list = new java.util.ArrayList<>(values.length);
        for (double value : values) {
            list.add(value);
        }
        return list;
    }

    public double mspt() {
        return Bukkit.getServer().getAverageTickTime();
    }

    public double lastTickTime() {
        return plugin.getLastTickTimeMs();
    }

    public int queueLen() {
        return plugin.getQueueLen();
    }
}
