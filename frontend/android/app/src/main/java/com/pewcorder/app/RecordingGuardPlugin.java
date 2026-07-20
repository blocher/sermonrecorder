package com.pewcorder.app;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "RecordingGuard")
public class RecordingGuardPlugin extends Plugin {
    @PluginMethod
    public void start(PluginCall call) {
        try {
            RecordingGuardService.start(getContext());
            call.resolve();
        } catch (RuntimeException error) {
            call.reject("Android could not keep the recording active in the background.", error);
        }
    }

    @PluginMethod
    public void stop(PluginCall call) {
        RecordingGuardService.stop(getContext());
        call.resolve();
    }

    @Override
    protected void handleOnDestroy() {
        RecordingGuardService.stop(getContext());
        super.handleOnDestroy();
    }
}
