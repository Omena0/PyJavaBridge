package com.pyjavabridge.util;

import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;

@FunctionalInterface
public interface NonLivingSpawner {
    Entity spawn(World world, Location location, EntityType entityType) throws Exception;
}
