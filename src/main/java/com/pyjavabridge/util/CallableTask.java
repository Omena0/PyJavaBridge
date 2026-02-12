package com.pyjavabridge.util;

@FunctionalInterface
public interface CallableTask {
    Object call() throws Exception;
}
