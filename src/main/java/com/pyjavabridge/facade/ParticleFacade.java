package com.pyjavabridge.facade;

import com.pyjavabridge.util.EnumValue;

import org.bukkit.World;

public class ParticleFacade {
    private static final int MAX_PARTICLES = 65536;

    private org.bukkit.Particle resolveParticle(Object obj) {
        if (obj instanceof org.bukkit.Particle p) return p;
        String name = null;
        if (obj instanceof EnumValue ev) name = ev.name;
        else if (obj instanceof String s) name = s;
        if (name == null) return null;
        try { return org.bukkit.Particle.valueOf(name.toUpperCase()); } catch (IllegalArgumentException e) {
            return null;
        }
    }

    public int line(World world, Object particleObj,
            double x1, double y1, double z1,
            double x2, double y2, double z2,
            double density,
            double offsetX, double offsetY, double offsetZ, double extra) {
        org.bukkit.Particle particle = resolveParticle(particleObj);
        if (particle == null) throw new IllegalArgumentException("Invalid particle");
        double dx = x2 - x1, dy = y2 - y1, dz = z2 - z1;
        double length = Math.sqrt(dx * dx + dy * dy + dz * dz);
        int count = Math.min(MAX_PARTICLES, Math.max(2, (int)(length * density)));
        for (int i = 0; i <= count; i++) {
            double t = (double) i / count;
            world.spawnParticle(particle, x1 + dx * t, y1 + dy * t, z1 + dz * t, 1, offsetX, offsetY, offsetZ, extra);
        }
        return count + 1;
    }

    public int sphere(World world, Object particleObj,
            double cx, double cy, double cz,
            double radius, double density, boolean hollow,
            double offsetX, double offsetY, double offsetZ, double extra) {
        org.bukkit.Particle particle = resolveParticle(particleObj);
        if (particle == null) throw new IllegalArgumentException("Invalid particle");
        int count = 0;
        if (hollow) {
            int n = Math.min(MAX_PARTICLES, Math.max(10, (int)(4 * Math.PI * radius * radius * density)));
            double goldenAngle = Math.PI * (3 - Math.sqrt(5));
            for (int i = 0; i < n; i++) {
                double theta = goldenAngle * i;
                double phi = Math.acos(1 - 2.0 * (i + 0.5) / n);
                double x = cx + radius * Math.sin(phi) * Math.cos(theta);
                double y = cy + radius * Math.cos(phi);
                double z = cz + radius * Math.sin(phi) * Math.sin(theta);
                world.spawnParticle(particle, x, y, z, 1, offsetX, offsetY, offsetZ, extra);
                count++;
            }
        } else {
            double step = 1.0 / Math.max(0.1, density);
            for (double x = -radius; x <= radius; x += step)
                for (double y = -radius; y <= radius; y += step)
                    for (double z = -radius; z <= radius; z += step) {
                        if (x * x + y * y + z * z <= radius * radius) {
                            if (count >= MAX_PARTICLES) return count;
                            world.spawnParticle(particle, cx + x, cy + y, cz + z, 1, offsetX, offsetY, offsetZ, extra);
                            count++;
                        }
                    }
        }
        return count;
    }

    public int cube(World world, Object particleObj,
            double x1, double y1, double z1,
            double x2, double y2, double z2,
            double density, boolean hollow,
            double offsetX, double offsetY, double offsetZ, double extra) {
        org.bukkit.Particle particle = resolveParticle(particleObj);
        if (particle == null) throw new IllegalArgumentException("Invalid particle");
        double minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
        double minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
        double minZ = Math.min(z1, z2), maxZ = Math.max(z1, z2);
        double step = 1.0 / Math.max(0.1, density);
        int count = 0;
        for (double x = minX; x <= maxX; x += step)
            for (double y = minY; y <= maxY; y += step)
                for (double z = minZ; z <= maxZ; z += step) {
                    boolean edge = Math.abs(x - minX) < step || Math.abs(x - maxX) < step
                            || Math.abs(y - minY) < step || Math.abs(y - maxY) < step
                            || Math.abs(z - minZ) < step || Math.abs(z - maxZ) < step;
                    if (!hollow || edge) {
                        if (count >= MAX_PARTICLES) return count;
                        world.spawnParticle(particle, x, y, z, 1, offsetX, offsetY, offsetZ, extra);
                        count++;
                    }
                }
        return count;
    }

    public int ring(World world, Object particleObj,
            double cx, double cy, double cz,
            double radius, double density,
            double offsetX, double offsetY, double offsetZ, double extra) {
        org.bukkit.Particle particle = resolveParticle(particleObj);
        if (particle == null) throw new IllegalArgumentException("Invalid particle");
        int count = Math.min(MAX_PARTICLES, Math.max(8, (int)(2 * Math.PI * radius * density)));
        for (int i = 0; i < count; i++) {
            double angle = 2 * Math.PI * i / count;
            double x = cx + radius * Math.cos(angle);
            double z = cz + radius * Math.sin(angle);
            world.spawnParticle(particle, x, cy, z, 1, offsetX, offsetY, offsetZ, extra);
        }
        return count;
    }
}
