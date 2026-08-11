package com.pewcorder.app;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "UploadKeepAlive")
public class UploadKeepAlivePlugin extends Plugin {
    @PluginMethod
    public void start(PluginCall call) {
        try {
            UploadKeepAliveService.start(getContext());
            call.resolve();
        } catch (RuntimeException error) {
            call.reject("Android could not keep the upload active in the background.", error);
        }
    }

    @PluginMethod
    public void stop(PluginCall call) {
        UploadKeepAliveService.stop(getContext());
        call.resolve();
    }

    @Override
    protected void handleOnDestroy() {
        UploadKeepAliveService.stop(getContext());
        super.handleOnDestroy();
    }
}
