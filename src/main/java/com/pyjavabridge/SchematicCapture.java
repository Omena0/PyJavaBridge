package com.pyjavabridge;

import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Container;
import org.bukkit.entity.Player;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Captures a region of blocks in-world and writes a .bschem (bridge schematic) file.
 * Concrete blocks are auto-detected as exits (lime) or markers (other colours).
 */
public final class SchematicCapture {

    private SchematicCapture() {}

    /**
     * Execute the /bridge schem command for the given player.
     *
     * @return true if the command was handled (even on error)
     */
    public static boolean handleCommand(Player player, String[] args, Path dataFolder) {
        if (args.length < 7) {
            player.sendMessage("\u00a7eUsage: /bridge schem <x> <y> <z> <width> <height> <depth>");
            return true;
        }
        try {
            int bx = Integer.parseInt(args[1]);
            int by = Integer.parseInt(args[2]);
            int bz = Integer.parseInt(args[3]);
            int width = Integer.parseInt(args[4]);
            int height = Integer.parseInt(args[5]);
            int depth = Integer.parseInt(args[6]);

            if (width <= 0 || height <= 0 || depth <= 0) {
                player.sendMessage("\u00a7cDimensions must be positive.");
                return true;
            }
            long volume = (long) width * height * depth;
            if (volume > 100000) {
                player.sendMessage("\u00a7cRegion too large (max 100,000 blocks).");
                return true;
            }

            World world = player.getWorld();

            // First pass: collect unique block strings and loot tags
            Map<String, String> lootTags = new HashMap<>(16);
            Map<String, Character> keyMap = new LinkedHashMap<>(64);
            List<String> blockDefs = new ArrayList<>((int) volume);
            String keyPool = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()_+-={}|[]:<>?,./";
            int nextKey = 0;

            Set<Integer> limeConcretePos = new HashSet<>(1024);
            Map<String, Set<Integer>> otherConcretePos = new LinkedHashMap<>(32);
            Map<String, Integer> blockCounts = new HashMap<>(256);

            for (int y = 0; y < height; y++) {
                for (int z = 0; z < depth; z++) {
                    for (int x = 0; x < width; x++) {
                        Block block = world.getBlockAt(bx + x, by + y, bz + z);
                        Material mat = block.getType();

                        if (mat == Material.AIR) {
                            blockDefs.add("air");
                            continue;
                        }

                        String matName = mat.name();
                        if (matName.endsWith("_CONCRETE")) {
                            int flatIdx = y * depth * width + z * width + x;
                            if (mat == Material.LIME_CONCRETE) {
                                limeConcretePos.add(flatIdx);
                                blockDefs.add("air");
                            } else {
                                String color = matName.substring(0, matName.length() - 9).toLowerCase();
                                otherConcretePos.computeIfAbsent(color, k -> new HashSet<>()).add(flatIdx);
                                blockDefs.add(null);
                            }
                            continue;
                        }

                        String data = block.getBlockData().getAsString();
                        String def = data;
                        if (def.startsWith("minecraft:")) {
                            def = def.substring("minecraft:".length());
                        }

                        BlockState state = block.getState();
                        if (state instanceof Container container) {
                            String customName = null;
                            try {
                                var displayName = container.customName();
                                if (displayName != null) {
                                    customName = net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer.plainText().serialize(displayName);
                                }
                            } catch (Exception e) {
                                try {
                                    customName = container.getInventory().getType().name();
                                } catch (Exception ignored) {}
                            }
                            if (customName != null && customName.contains("[loot:")) {
                                java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\[loot:(\\w+)\\]").matcher(customName);
                                if (m.find()) {
                                    String tag = m.group(1);
                                    lootTags.put(tag, tag);
                                    if (def.contains("[")) {
                                        def = def.substring(0, def.length() - 1) + ",name=[loot:" + tag + "]]";
                                    } else {
                                        def = def + "[name=[loot:" + tag + "]]";
                                    }
                                }
                            }
                        }

                        if (!def.equals("air") && !keyMap.containsKey(def)) {
                            if (nextKey >= keyPool.length()) {
                                player.sendMessage("\u00a7cToo many unique block types (max " + keyPool.length() + ").");
                                return true;
                            }
                            keyMap.put(def, keyPool.charAt(nextKey++));
                        }
                        if (!def.equals("air")) blockCounts.merge(def, 1, (a, b) -> a + b);
                        blockDefs.add(def);
                    }
                }
            }

            // Compute main block(s)
            int totalNonAir = 0;
            for (int count : blockCounts.values()) {
                totalNonAir += count;
            }
            List<String> mainBlockDefs = new ArrayList<>(8);
            List<Integer> mainBlockWeights = new ArrayList<>(8);
            if (totalNonAir > 0) {
                List<Map.Entry<String, Integer>> sorted = new ArrayList<>(blockCounts.entrySet());
                sorted.sort((a, b) -> Integer.compare(b.getValue(), a.getValue()));
                for (var entry : sorted) {
                    double pct = (double) entry.getValue() / totalNonAir * 100;
                    if (pct >= 35.0) {
                        mainBlockDefs.add(entry.getKey());
                        mainBlockWeights.add(entry.getValue());
                    }
                }
                if (mainBlockDefs.isEmpty()) {
                    mainBlockDefs.add(sorted.get(0).getKey());
                    mainBlockWeights.add(sorted.get(0).getValue());
                }
            } else {
                mainBlockDefs.add("stone");
                mainBlockWeights.add(1);
            }

            for (String mainDef : mainBlockDefs) {
                if (!mainDef.equals("air") && !keyMap.containsKey(mainDef)) {
                    if (nextKey >= keyPool.length()) {
                        player.sendMessage("\u00a7cToo many unique block types.");
                        return true;
                    }
                    keyMap.put(mainDef, keyPool.charAt(nextKey++));
                }
            }

            // Replace concrete marker placeholders with main block(s)
            if (!otherConcretePos.isEmpty()) {
                int totalWeight = 0;
                for (int weight : mainBlockWeights) {
                    totalWeight += weight;
                }
                for (int i = 0; i < blockDefs.size(); i++) {
                    if (blockDefs.get(i) == null) {
                        if (mainBlockDefs.size() == 1) {
                            blockDefs.set(i, mainBlockDefs.get(0));
                        } else {
                            int px = i % width;
                            int pz = (i / width) % depth;
                            int py = i / (width * depth);
                            int hash = (px * 73856093) ^ (py * 19349669) ^ (pz * 83492791);
                            int pick = (hash & 0x7FFFFFFF) % totalWeight;
                            int cumulative = 0;
                            String chosen = mainBlockDefs.get(0);
                            for (int j = 0; j < mainBlockDefs.size(); j++) {
                                cumulative += mainBlockWeights.get(j);
                                if (pick < cumulative) {
                                    chosen = mainBlockDefs.get(j);
                                    break;
                                }
                            }
                            blockDefs.set(i, chosen);
                        }
                    }
                }
            }

            // Detect exits from lime concrete groups
            List<String> exitDefs = new ArrayList<>(8);
            if (!limeConcretePos.isEmpty()) {
                for (Set<Integer> group : connectedComponents(limeConcretePos, width, height, depth)) {
                    String exitDef = exitFromGroup(group, width, height, depth);
                    if (exitDef != null) exitDefs.add(exitDef);
                }
            }

            // Detect markers from other concrete groups
            List<String> markerDefs = new ArrayList<>(otherConcretePos.size() * 2);
            for (var colorEntry : otherConcretePos.entrySet()) {
                for (Set<Integer> group : connectedComponents(colorEntry.getValue(), width, height, depth)) {
                    String mDef = markerFromGroup(colorEntry.getKey(), group, width, height, depth);
                    if (mDef != null) markerDefs.add(mDef);
                }
            }

            // Build a 3-D key char array [y][z][x] for encoding
            char[][][] grid = new char[height][depth][width];
            int idx = 0;
            for (int y = 0; y < height; y++)
                for (int z = 0; z < depth; z++)
                    for (int x = 0; x < width; x++)
                        grid[y][z][x] = blockDefs.get(idx++).equals("air") ? '~' : keyMap.get(blockDefs.get(idx - 1));

            // Encode with multi-phase algorithm (volumetric fills + greedy mesh)
            List<String> opsList = encodeOps(grid, width, height, depth);
            StringBuilder ops = new StringBuilder();
            for (String op : opsList) ops.append(op).append('\n');

            // Build full .bschem content
            StringBuilder bschem = new StringBuilder();
            bschem.append("type: generic\n");
            bschem.append("width: ").append(width).append("\n");
            bschem.append("height: ").append(height).append("\n");
            bschem.append("depth: ").append(depth).append("\n");
            if (!lootTags.isEmpty()) {
                bschem.append("loot:");
                for (var entry : lootTags.entrySet()) {
                    bschem.append(" ").append(entry.getKey()).append("=").append(entry.getValue());
                }
                bschem.append("\n");
            }
            bschem.append("\n");

            for (String exitDef : exitDefs) {
                bschem.append("exit: ").append(exitDef).append("\n");
            }
            for (String markerDef : markerDefs) {
                bschem.append("marker: ").append(markerDef).append("\n");
            }
            if (!exitDefs.isEmpty() || !markerDefs.isEmpty()) bschem.append("\n");

            // Key definitions
            for (var entry : keyMap.entrySet()) {
                bschem.append(entry.getValue()).append(": ").append(entry.getKey()).append("\n");
            }
            bschem.append("\n---\n");
            bschem.append(ops);

            // Write to file
            Path outputDir = dataFolder.resolve("schematics");
            Files.createDirectories(outputDir);
            String filename = "schem_" + bx + "_" + by + "_" + bz + ".bschem";
            Path outputFile = outputDir.resolve(filename);
            Files.writeString(outputFile, bschem.toString(), StandardCharsets.UTF_8);

            player.sendMessage("\u00a7aSchematic saved to " + outputFile.toAbsolutePath());
            player.sendMessage("\u00a77Size: " + width + "x" + height + "x" + depth + " (" + volume + " blocks, " + keyMap.size() + " unique types)");
            if (!lootTags.isEmpty()) {
                player.sendMessage("\u00a77Loot tags found: " + String.join(", ", lootTags.keySet()));
            }
            if (!exitDefs.isEmpty()) {
                player.sendMessage("\u00a77Exits detected: " + exitDefs.size());
            }
            if (!markerDefs.isEmpty()) {
                player.sendMessage("\u00a77Markers detected: " + markerDefs.size());
            }
            if (!mainBlockDefs.isEmpty() && !otherConcretePos.isEmpty()) {
                player.sendMessage("\u00a77Main block(s): " + String.join(", ", mainBlockDefs));
            }

        } catch (NumberFormatException e) {
            player.sendMessage("\u00a7cCoordinates and dimensions must be integers.");
        } catch (Exception e) {
            player.sendMessage("\u00a7cError: " + e.getMessage());
        }
        return true;
    }

    /**
     * Provide tab-complete suggestions for the schem subcommand.
     */
    public static List<String> tabComplete(Player player, String[] args) {
        Block target = player.getTargetBlockExact(5);
        if (target != null) {
            return switch (args.length) {
                case 2 -> List.of(String.valueOf(target.getX()));
                case 3 -> List.of(String.valueOf(target.getY()));
                case 4 -> List.of(String.valueOf(target.getZ()));
                default -> List.of();
            };
        }
        return List.of();
    }

    // -- Encoding helpers ---------------------------------------------------------

    /**
     * Encode a 3-D char grid into fill/set operations using a two-phase
     * algorithm: volumetric fills with overwriting, then greedy meshing.
     */
    static List<String> encodeOps(char[][][] target, int w, int h, int d) {
        char[][][] state = new char[h][d][w];
        for (int y = 0; y < h; y++)
            for (int z = 0; z < d; z++)
                java.util.Arrays.fill(state[y][z], '~');

        List<String> phase1 = new ArrayList<>(64);
        List<String> baseline = Objects.requireNonNull(greedyMesh(target, state, w, h, d));

        while (true) {
            List<Object[]> candidates = diffCandidates(target, state, w, h, d);
            if (candidates.isEmpty()) break;

            int currentTotal = phase1.size() + baseline.size();
            String bestOp = null;
            char[][][] bestState = null;
            List<String> bestCorr = null;
            int bestTotal = currentTotal;

            for (Object[] cand : candidates) {
                char key = (char) cand[0];
                int[] b = (int[]) cand[1];
                int vol = (b[3]-b[0]+1) * (b[4]-b[1]+1) * (b[5]-b[2]+1);
                if (vol <= 1) continue;

                char[][][] trial = copyState(state, h, d, w);
                for (int y = b[1]; y <= b[4]; y++)
                    for (int z = b[2]; z <= b[5]; z++)
                        for (int x = b[0]; x <= b[3]; x++)
                            trial[y][z][x] = key;

                List<String> trialCorr = greedyMesh(target, trial, w, h, d);
                int trialTotal = phase1.size() + 1 + trialCorr.size();
                if (trialTotal < bestTotal) {
                    bestTotal = trialTotal;
                    bestOp = "fill " + b[0] + " " + b[1] + " " + b[2] + " " + b[3] + " " + b[4] + " " + b[5] + " " + key;
                    bestState = trial;
                    bestCorr = trialCorr;
                }
            }

            if (bestOp == null) break;
            phase1.add(bestOp);
            state = bestState;
            baseline = Objects.requireNonNull(bestCorr);
        }

        List<String> result = new ArrayList<>(phase1);
        result.addAll(baseline);
        return result;
    }

    private static List<Object[]> diffCandidates(char[][][] target, char[][][] state, int w, int h, int d) {
        Map<Character, int[]> bboxes = new HashMap<>(256);
        for (int y = 0; y < h; y++)
            for (int z = 0; z < d; z++)
                for (int x = 0; x < w; x++) {
                    if (state[y][z][x] != target[y][z][x]) {
                        char k = target[y][z][x];
                        int[] b = bboxes.computeIfAbsent(k, c -> new int[]{w, h, d, -1, -1, -1});
                        if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y; if (z < b[2]) b[2] = z;
                        if (x > b[3]) b[3] = x; if (y > b[4]) b[4] = y; if (z > b[5]) b[5] = z;
                    }
                }
        List<Object[]> result = new ArrayList<>(bboxes.size() * 27);
        java.util.Set<Long> seen = new java.util.HashSet<>(bboxes.size() * 27);
        for (var entry : bboxes.entrySet()) {
            char k = entry.getKey();
            int[] b = entry.getValue();
            if (b[3] < 0) continue;
            int x1 = b[0], y1 = b[1], z1 = b[2], x2 = b[3], y2 = b[4], z2 = b[5];
            for (int xz = 0; xz < 3; xz++) {
                for (int yb = 0; yb < 3; yb++) {
                    for (int yt = 0; yt < 3; yt++) {
                        int nx1 = x1+xz, nz1 = z1+xz, nx2 = x2-xz, nz2 = z2-xz;
                        int ny1 = y1+yb, ny2 = y2-yt;
                        if (nx1 > nx2 || ny1 > ny2 || nz1 > nz2) continue;
                        long lkey = ((long)k << 48) | ((long)nx1<<40) | ((long)ny1<<32) |
                                   ((long)nz1<<24) | ((long)nx2<<16) | ((long)ny2<<8) | nz2;
                        if (seen.add(lkey))
                            result.add(new Object[]{k, new int[]{nx1, ny1, nz1, nx2, ny2, nz2}});
                    }
                }
            }
        }
        return result;
    }

    private static final int[][] SWEEP_PERMS = {{1,2,0}, {0,2,1}, {2,0,1}};

    private static List<String> greedyMesh(char[][][] target, char[][][] state, int w, int h, int d) {
        List<String> best = null;
        for (int[] perm : SWEEP_PERMS) {
            List<String> ops = greedySweep(target, state, w, h, d, perm);
            if (best == null || ops.size() < best.size()) best = ops;
        }
        return best;
    }

    private static List<String> greedySweep(char[][][] target, char[][][] state, int w, int h, int d, int[] perm) {
        int[] dims = {w, h, d};
        int s0 = dims[perm[0]], s1 = dims[perm[1]], s2 = dims[perm[2]];
        int p0 = perm[0], p1 = perm[1], p2 = perm[2];
        boolean[][][] visited = new boolean[s0][s1][s2];
        List<String> ops = new ArrayList<>(Math.max(64, (s0 * s1 * s2) / 100));

        for (int a = 0; a < s0; a++) {
            for (int b = 0; b < s1; b++) {
                for (int c = 0; c < s2; c++) {
                    if (visited[a][b][c]) continue;
                    int[] r = new int[3];
                    r[p0] = a; r[p1] = b; r[p2] = c;
                    int cx = r[0], cy = r[1], cz = r[2];
                    if (state[cy][cz][cx] == target[cy][cz][cx]) continue;
                    char key = target[cy][cz][cx];

                    int ec = c;
                    while (ec+1 < s2) {
                        int[] r2 = new int[3]; r2[p0]=a; r2[p1]=b; r2[p2]=ec+1;
                        int nx=r2[0], ny=r2[1], nz=r2[2];
                        if (visited[a][b][ec+1] || state[ny][nz][nx]==target[ny][nz][nx] || target[ny][nz][nx]!=key) break;
                        ec++;
                    }
                    int eb = b;
                    boolean exp = true;
                    while (exp && eb+1 < s1) {
                        for (int jc = c; jc <= ec; jc++) {
                            int[] r2 = new int[3]; r2[p0]=a; r2[p1]=eb+1; r2[p2]=jc;
                            int nx=r2[0], ny=r2[1], nz=r2[2];
                            if (visited[a][eb+1][jc] || state[ny][nz][nx]==target[ny][nz][nx] || target[ny][nz][nx]!=key) { exp=false; break; }
                        }
                        if (exp) eb++;
                    }
                    int ea = a;
                    exp = true;
                    while (exp && ea+1 < s0) {
                        for (int jb = b; jb <= eb && exp; jb++)
                            for (int jc = c; jc <= ec; jc++) {
                                int[] r2 = new int[3]; r2[p0]=ea+1; r2[p1]=jb; r2[p2]=jc;
                                int nx=r2[0], ny=r2[1], nz=r2[2];
                                if (visited[ea+1][jb][jc] || state[ny][nz][nx]==target[ny][nz][nx] || target[ny][nz][nx]!=key) { exp=false; break; }
                            }
                        if (exp) ea++;
                    }

                    for (int ja = a; ja <= ea; ja++)
                        for (int jb = b; jb <= eb; jb++)
                            for (int jc = c; jc <= ec; jc++)
                                visited[ja][jb][jc] = true;

                    int[] rs = new int[3]; rs[p0]=a; rs[p1]=b; rs[p2]=c;
                    int[] re = new int[3]; re[p0]=ea; re[p1]=eb; re[p2]=ec;
                    int x1=rs[0], y1=rs[1], z1=rs[2], x2=re[0], y2=re[1], z2=re[2];

                    if (x1==x2 && y1==y2 && z1==z2)
                        ops.add("set " + x1 + " " + y1 + " " + z1 + " " + key);
                    else
                        ops.add("fill " + x1 + " " + y1 + " " + z1 + " " + x2 + " " + y2 + " " + z2 + " " + key);
                }
            }
        }
        return ops;
    }

    private static char[][][] copyState(char[][][] state, int h, int d, int w) {
        char[][][] copy = new char[h][d][w];
        for (int y = 0; y < h; y++)
            for (int z = 0; z < d; z++)
                System.arraycopy(state[y][z], 0, copy[y][z], 0, w);
        return copy;
    }

    /** Find connected components via BFS in a set of flat-indexed positions. */
    static List<Set<Integer>> connectedComponents(Set<Integer> positions, int w, int h, int d) {
        List<Set<Integer>> components = new ArrayList<>(8);
        Set<Integer> remaining = new HashSet<>(positions);
        while (!remaining.isEmpty()) {
            int start = remaining.iterator().next();
            Set<Integer> comp = new HashSet<>(positions.size() / 4);
            ArrayDeque<Integer> queue = new ArrayDeque<>();
            queue.add(start);
            remaining.remove(start);
            while (!queue.isEmpty()) {
                int pos = queue.poll();
                comp.add(pos);
                int px = pos % w, pz = (pos / w) % d, py = pos / (w * d);
                int[][] nbrs = {{px-1,py,pz},{px+1,py,pz},{px,py-1,pz},{px,py+1,pz},{px,py,pz-1},{px,py,pz+1}};
                for (int[] n : nbrs) {
                    if (n[0] >= 0 && n[0] < w && n[1] >= 0 && n[1] < h && n[2] >= 0 && n[2] < d) {
                        int nIdx = n[1] * d * w + n[2] * w + n[0];
                        if (remaining.remove(nIdx)) queue.add(nIdx);
                    }
                }
            }
            components.add(comp);
        }
        return components;
    }

    /** Determine an exit definition from a connected group of lime concrete positions. */
    static String exitFromGroup(Set<Integer> group, int w, int h, int d) {
        int minX = w, maxX = -1, minY = h, maxY = -1, minZ = d, maxZ = -1;
        for (int pos : group) {
            int px = pos % w, pz = (pos / w) % d, py = pos / (w * d);
            if (px < minX) minX = px; if (px > maxX) maxX = px;
            if (py < minY) minY = py; if (py > maxY) maxY = py;
            if (pz < minZ) minZ = pz; if (pz > maxZ) maxZ = pz;
        }
        String facing; int ew, eh;
        if (minX == maxX) {
            facing = (minX == 0) ? "-x" : "+x";
            ew = maxZ - minZ + 1; eh = maxY - minY + 1;
        } else if (minZ == maxZ) {
            facing = (minZ == 0) ? "-z" : "+z";
            ew = maxX - minX + 1; eh = maxY - minY + 1;
        } else if (minY == maxY) {
            facing = (minY == 0) ? "-y" : "+y";
            ew = maxX - minX + 1; eh = maxZ - minZ + 1;
        } else {
            return null;
        }
        return minX + "," + minY + "," + minZ + " " + facing + " " + ew + "x" + eh;
    }

    /** Determine a marker definition from a connected group of concrete positions. */
    static String markerFromGroup(String color, Set<Integer> group, int w, int h, int d) {
        int minX = w, maxX = -1, minY = h, maxY = -1, minZ = d, maxZ = -1;
        for (int pos : group) {
            int px = pos % w, pz = (pos / w) % d, py = pos / (w * d);
            if (px < minX) minX = px; if (px > maxX) maxX = px;
            if (py < minY) minY = py; if (py > maxY) maxY = py;
            if (pz < minZ) minZ = pz; if (pz > maxZ) maxZ = pz;
        }
        return color + " " + minX + "," + minY + "," + minZ + " " +
               (maxX - minX + 1) + "x" + (maxY - minY + 1) + "x" + (maxZ - minZ + 1);
    }
}
