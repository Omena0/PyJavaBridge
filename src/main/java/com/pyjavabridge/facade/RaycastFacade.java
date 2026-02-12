package com.pyjavabridge.facade;

import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.Map;

public class RaycastFacade {
    public Map<String, Object> trace(World world, double startX, double startY, double startZ,
            Float yaw, Float pitch, double maxDistance, double raySize,
            boolean includeEntities, boolean includeBlocks, boolean ignorePassable) {
        if (world == null) {
            return null;
        }
        if (!includeEntities && !includeBlocks) {
            return null;
        }
        Vector direction;
        if (yaw != null && pitch != null) {
            direction = new Location(world, startX, startY, startZ, yaw, pitch).getDirection();
        } else {
            return null;
        }
        if (direction.lengthSquared() == 0) {
            return null;
        }
        direction.normalize();

        Location start = new Location(world, startX, startY, startZ);

        RayTraceResult result;

        if (includeBlocks && includeEntities) {
            result = world.rayTrace(start, direction, maxDistance, FluidCollisionMode.NEVER, ignorePassable,
                    raySize, entity -> true);
        } else if (includeBlocks) {
            result = world.rayTraceBlocks(start, direction, maxDistance, FluidCollisionMode.NEVER,
                    ignorePassable);
        } else {
            result = world.rayTraceEntities(start, direction, maxDistance, raySize, entity -> true);
        }

        Vector hitPosition = result != null ? result.getHitPosition() : null;
        if (hitPosition == null) {
            hitPosition = start.toVector().add(direction.clone().multiply(maxDistance));
        }
        double hitX = hitPosition.getX();
        double hitY = hitPosition.getY();
        double hitZ = hitPosition.getZ();
        float outYaw = yaw != null ? yaw
                : (float) Math.toDegrees(Math.atan2(-direction.getX(), direction.getZ()));
        float outPitch = pitch != null ? pitch : (float) Math.toDegrees(Math.asin(-direction.getY()));
        Block hitBlock = result != null ? result.getHitBlock() : null;
        Entity hitEntity = result != null ? result.getHitEntity() : null;
        Map<String, Object> payload = new HashMap<>();

        payload.put("x", hitX);
        payload.put("y", hitY);
        payload.put("z", hitZ);
        payload.put("entity", hitEntity);
        payload.put("block", hitBlock);
        payload.put("startX", startX);
        payload.put("startY", startY);
        payload.put("startZ", startZ);
        payload.put("yaw", outYaw);
        payload.put("pitch", outPitch);

        double ddx = hitX - startX;
        double ddy = hitY - startY;
        double ddz = hitZ - startZ;
        payload.put("distance", Math.sqrt(ddx * ddx + ddy * ddy + ddz * ddz));

        if (result != null && result.getHitBlockFace() != null) {
            payload.put("hit_face", result.getHitBlockFace().name());
        }

        return payload;
    }
}
