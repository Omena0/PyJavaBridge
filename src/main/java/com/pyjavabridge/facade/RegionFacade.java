package com.pyjavabridge.facade;

import com.pyjavabridge.util.EnumValue;

import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;

import java.util.HashSet;
import java.util.Set;

public class RegionFacade {
    private static final long MAX_VOLUME = 2048L * 2048L * 2048L;

    private Material resolveMat(Object obj) {
        if (obj instanceof Material m) return m;
        if (obj instanceof EnumValue ev) return Material.matchMaterial(ev.name);
        if (obj instanceof String s) return Material.matchMaterial(s);
        return null;
    }

    private void checkVolume(long volume) {
        if (volume > MAX_VOLUME) {
            throw new IllegalArgumentException("Region volume " + volume + " exceeds maximum of " + MAX_VOLUME);
        }
    }

    public int setBlock(World world, int x, int y, int z, Object material, boolean applyPhysics) {
        Material mat = resolveMat(material);
        if (mat == null) throw new IllegalArgumentException("Invalid material");
        world.getBlockAt(x, y, z).setType(mat, applyPhysics);
        return 1;
    }

    public int fill(World world, int x1, int y1, int z1, int x2, int y2, int z2, Object material, boolean applyPhysics) {
        Material mat = resolveMat(material);
        if (mat == null) throw new IllegalArgumentException("Invalid material");
        int minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
        int minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
        int minZ = Math.min(z1, z2), maxZ = Math.max(z1, z2);
        long volume = (long)(maxX - minX + 1) * (maxY - minY + 1) * (maxZ - minZ + 1);
        checkVolume(volume);
        int count = 0;
        for (int x = minX; x <= maxX; x++)
            for (int y = minY; y <= maxY; y++)
                for (int z = minZ; z <= maxZ; z++) {
                    world.getBlockAt(x, y, z).setType(mat, applyPhysics);
                    count++;
                }
        return count;
    }

    public int replace(World world, int x1, int y1, int z1, int x2, int y2, int z2, Object fromMaterial, Object toMaterial) {
        Material from = resolveMat(fromMaterial);
        Material to = resolveMat(toMaterial);
        if (from == null || to == null) throw new IllegalArgumentException("Invalid material");
        int minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
        int minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
        int minZ = Math.min(z1, z2), maxZ = Math.max(z1, z2);
        long volume = (long)(maxX - minX + 1) * (maxY - minY + 1) * (maxZ - minZ + 1);
        checkVolume(volume);
        int count = 0;
        for (int x = minX; x <= maxX; x++)
            for (int y = minY; y <= maxY; y++)
                for (int z = minZ; z <= maxZ; z++) {
                    Block b = world.getBlockAt(x, y, z);
                    if (b.getType() == from) {
                        b.setType(to, false);
                        count++;
                    }
                }
        return count;
    }

    public int sphere(World world, double cx, double cy, double cz, double radius, Object material, boolean hollow) {
        Material mat = resolveMat(material);
        if (mat == null) throw new IllegalArgumentException("Invalid material");
        int r = (int) Math.ceil(radius);
        double r2 = radius * radius;
        double inner2 = hollow ? (radius - 1) * (radius - 1) : -1;
        long approxVolume = (long)(2 * r + 1) * (2 * r + 1) * (2 * r + 1);
        checkVolume(approxVolume);
        int count = 0;
        for (int x = -r; x <= r; x++)
            for (int y = -r; y <= r; y++)
                for (int z = -r; z <= r; z++) {
                    double dist2 = x * x + y * y + z * z;
                    if (dist2 <= r2 && (!hollow || dist2 >= inner2)) {
                        world.getBlockAt((int)(cx + x), (int)(cy + y), (int)(cz + z)).setType(mat, false);
                        count++;
                    }
                }
        return count;
    }

    public int cylinder(World world, double cx, double cy, double cz, double radius, int height, Object material, boolean hollow) {
        Material mat = resolveMat(material);
        if (mat == null) throw new IllegalArgumentException("Invalid material");
        int r = (int) Math.ceil(radius);
        double r2 = radius * radius;
        double inner2 = hollow ? (radius - 1) * (radius - 1) : -1;
        long approxVolume = (long)(2 * r + 1) * (2 * r + 1) * height;
        checkVolume(approxVolume);
        int count = 0;
        for (int x = -r; x <= r; x++)
            for (int z = -r; z <= r; z++) {
                double dist2 = x * x + z * z;
                if (dist2 <= r2 && (!hollow || dist2 >= inner2)) {
                    for (int y = 0; y < height; y++) {
                        world.getBlockAt((int)(cx + x), (int)(cy + y), (int)(cz + z)).setType(mat, false);
                        count++;
                    }
                }
            }
        return count;
    }

    public int line(World world, double x1, double y1, double z1, double x2, double y2, double z2, Object material) {
        Material mat = resolveMat(material);
        if (mat == null) throw new IllegalArgumentException("Invalid material");
        double dx = x2 - x1, dy = y2 - y1, dz = z2 - z1;
        double length = Math.sqrt(dx * dx + dy * dy + dz * dz);
        int steps = Math.max(1, (int) Math.ceil(length));
        Set<Long> placed = new HashSet<>();
        int count = 0;
        for (int i = 0; i <= steps; i++) {
            double t = (double) i / steps;
            int bx = (int) Math.floor(x1 + dx * t);
            int by = (int) Math.floor(y1 + dy * t);
            int bz = (int) Math.floor(z1 + dz * t);
            long key = ((long) bx & 0x3FFFFFFL) << 38 | ((long) by & 0xFFFL) << 26 | ((long) bz & 0x3FFFFFFL);
            if (placed.add(key)) {
                world.getBlockAt(bx, by, bz).setType(mat, false);
                count++;
            }
        }
        return count;
    }
}
