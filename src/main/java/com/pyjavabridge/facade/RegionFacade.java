package com.pyjavabridge.facade;

import com.pyjavabridge.util.EnumValue;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Nameable;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.BlockData;

import net.kyori.adventure.text.Component;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class RegionFacade {
    private static final long MAX_VOLUME = 1_000_000L;

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
        if (mat == null) {
            String info = material == null ? "null" : material.getClass().getName() + "='" + material + "'";
            if (material instanceof EnumValue ev) info = "EnumValue(type='" + ev.type + "', name='" + ev.name + "')";
            throw new IllegalArgumentException("Invalid material: " + info);
        }
        world.getBlockAt(x, y, z).setType(mat, applyPhysics);
        return 1;
    }

    public int fill(World world, int x1, int y1, int z1, int x2, int y2, int z2, Object material, boolean applyPhysics) {
        Material mat = resolveMat(material);
        if (mat == null) {
            String info = material == null ? "null" : material.getClass().getName() + "='" + material + "'";
            if (material instanceof EnumValue ev) info = "EnumValue(type='" + ev.type + "', name='" + ev.name + "')";
            throw new IllegalArgumentException("Invalid material: " + info);
        }
        int minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
        int minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
        int minZ = Math.min(z1, z2), maxZ = Math.max(z1, z2);
        long volume = (long)(maxX - minX + 1) * (maxY - minY + 1) * (maxZ - minZ + 1);
        checkVolume(volume);
        return fillChunkBatched(world, minX, minY, minZ, maxX, maxY, maxZ, mat, applyPhysics);
    }

    private int fillChunkBatched(World world, int minX, int minY, int minZ, int maxX, int maxY, int maxZ, Material mat, boolean applyPhysics) {
        int count = 0;
        int chunkMinX = minX >> 4;
        int chunkMaxX = maxX >> 4;
        int chunkMinZ = minZ >> 4;
        int chunkMaxZ = maxZ >> 4;

        for (int cx = chunkMinX; cx <= chunkMaxX; cx++) {
            for (int cz = chunkMinZ; cz <= chunkMaxZ; cz++) {
                int startX = Math.max(minX, cx << 4);
                int endX = Math.min(maxX, (cx << 4) + 15);
                int startZ = Math.max(minZ, cz << 4);
                int endZ = Math.min(maxZ, (cz << 4) + 15);

                if (!world.isChunkLoaded(cx, cz)) {
                    world.getChunkAt(cx, cz);
                }

                for (int x = startX; x <= endX; x++)
                    for (int y = minY; y <= maxY; y++)
                        for (int z = startZ; z <= endZ; z++) {
                            world.getBlockAt(x, y, z).setType(mat, applyPhysics);
                            count++;
                        }
            }
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
        return replaceChunkBatched(world, minX, minY, minZ, maxX, maxY, maxZ, from, to);
    }

    private int replaceChunkBatched(World world, int minX, int minY, int minZ, int maxX, int maxY, int maxZ, Material from, Material to) {
        int count = 0;
        int chunkMinX = minX >> 4;
        int chunkMaxX = maxX >> 4;
        int chunkMinZ = minZ >> 4;
        int chunkMaxZ = maxZ >> 4;

        for (int cx = chunkMinX; cx <= chunkMaxX; cx++) {
            for (int cz = chunkMinZ; cz <= chunkMaxZ; cz++) {
                int startX = Math.max(minX, cx << 4);
                int endX = Math.min(maxX, (cx << 4) + 15);
                int startZ = Math.max(minZ, cz << 4);
                int endZ = Math.min(maxZ, (cz << 4) + 15);

                if (!world.isChunkLoaded(cx, cz)) {
                    world.getChunkAt(cx, cz);
                }

                for (int x = startX; x <= endX; x++)
                    for (int y = minY; y <= maxY; y++)
                        for (int z = startZ; z <= endZ; z++) {
                            Block b = world.getBlockAt(x, y, z);
                            if (b.getType() == from) {
                                b.setType(to, false);
                                count++;
                            }
                        }
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

    /**
     * Execute a batch of fill/set operations in one call and return the original block states.
     * <p>
     * Each operation is a List: ["set", x, y, z, "minecraft:block[state]"]
     * or ["fill", x1, y1, z1, x2, y2, z2, "minecraft:block[state]"]
     * <p>
     * Returns a Map of "x:y:z" → "blockdata_string" for all blocks that were modified.
     */
    @SuppressWarnings("unchecked")
    public Map<String, String> pasteOperations(World world, List<Object> operations) {
        Map<String, String> originals = new HashMap<>();

        for (Object opObj : operations) {
            List<Object> op = (List<Object>) opObj;
            String type = (String) op.get(0);

            if ("set".equals(type)) {
                int x = ((Number) op.get(1)).intValue();
                int y = ((Number) op.get(2)).intValue();
                int z = ((Number) op.get(3)).intValue();
                String blockStr = (String) op.get(4);

                Block block = world.getBlockAt(x, y, z);
                String key = x + ":" + y + ":" + z;
                if (!originals.containsKey(key)) {
                    originals.put(key, block.getBlockData().getAsString());
                }

                applyBlockData(block, blockStr);

            } else if ("fill".equals(type)) {
                int x1 = ((Number) op.get(1)).intValue();
                int y1 = ((Number) op.get(2)).intValue();
                int z1 = ((Number) op.get(3)).intValue();
                int x2 = ((Number) op.get(4)).intValue();
                int y2 = ((Number) op.get(5)).intValue();
                int z2 = ((Number) op.get(6)).intValue();
                String blockStr = (String) op.get(7);

                int minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
                int minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
                int minZ = Math.min(z1, z2), maxZ = Math.max(z1, z2);

                // Pre-parse block data for the fill (handles name extraction)
                String customName = null;
                String cleanStr = blockStr;
                Matcher fm = NAME_PATTERN.matcher(blockStr);
                if (fm.find()) {
                    customName = fm.group(1);
                    cleanStr = fm.replaceFirst("");
                    cleanStr = cleanStr.replace("[,", "[").replace(",]", "]");
                    if (cleanStr.endsWith("[]")) {
                        cleanStr = cleanStr.substring(0, cleanStr.length() - 2);
                    }
                }
                BlockData data;
                try {
                    data = Bukkit.createBlockData(cleanStr.toLowerCase());
                } catch (IllegalArgumentException e) {
                    String matName = cleanStr.contains("[") ? cleanStr.substring(0, cleanStr.indexOf('[')) : cleanStr;
                    Material mat = Material.matchMaterial(matName);
                    data = mat != null ? mat.createBlockData() : Material.AIR.createBlockData();
                }

                for (int bx = minX; bx <= maxX; bx++) {
                    for (int by = minY; by <= maxY; by++) {
                        for (int bz = minZ; bz <= maxZ; bz++) {
                            Block block = world.getBlockAt(bx, by, bz);
                            String key = bx + ":" + by + ":" + bz;
                            if (!originals.containsKey(key)) {
                                originals.put(key, block.getBlockData().getAsString());
                            }
                            block.setBlockData(data, false);
                            if (customName != null) {
                                BlockState state = block.getState();
                                if (state instanceof Nameable nameable) {
                                    nameable.customName(Component.text(customName));
                                    state.update();
                                }
                            }
                        }
                    }
                }
            }
        }

        return originals;
    }

    /**
     * Restore blocks from a saved originals list (from pasteOperations).
     * Each entry is [x, y, z, "blockdata_string"].
     */
    @SuppressWarnings("unchecked")
    public int restoreBlocks(World world, List<Object> originals) {
        int count = 0;
        for (Object entryObj : originals) {
            List<Object> entry = (List<Object>) entryObj;
            int x = ((Number) entry.get(0)).intValue();
            int y = ((Number) entry.get(1)).intValue();
            int z = ((Number) entry.get(2)).intValue();
            String blockStr = (String) entry.get(3);

            Block block = world.getBlockAt(x, y, z);
            applyBlockData(block, blockStr);
            count++;
        }
        return count;
    }

    private static final Pattern NAME_PATTERN = Pattern.compile(",?name=(\\[[^\\]]+\\])");

    private void applyBlockData(Block block, String blockStr) {
        String customName = null;
        String cleanStr = blockStr;

        // Extract name=[...] from block data string (not a real block state)
        Matcher m = NAME_PATTERN.matcher(blockStr);
        if (m.find()) {
            customName = m.group(1);  // includes brackets, e.g. "[loot:chest1]"
            cleanStr = m.replaceFirst("");
            // Clean up trailing/leading commas in brackets
            cleanStr = cleanStr.replace("[,", "[").replace(",]", "]");
            if (cleanStr.endsWith("[]")) {
                cleanStr = cleanStr.substring(0, cleanStr.length() - 2);
            }
        }

        try {
            block.setBlockData(Bukkit.createBlockData(cleanStr.toLowerCase()), false);
        } catch (IllegalArgumentException e) {
            // Fallback: try just the material
            String matName = cleanStr.contains("[") ? cleanStr.substring(0, cleanStr.indexOf('[')) : cleanStr;
            Material mat = Material.matchMaterial(matName);
            if (mat != null) {
                block.setType(mat, false);
            }
        }

        if (customName != null) {
            BlockState state = block.getState();
            if (state instanceof Nameable nameable) {
                nameable.customName(Component.text(customName));
                state.update();
            }
        }
    }
}
