package com.dawasafe.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.view.View;
import android.view.WindowInsets;

public class MainActivity extends Activity {
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private Uri pendingCameraUri;
    private PermissionRequest pendingWebPermission;
    private static final int REQ_FILE = 501;
    private static final int REQ_CAMERA = 502;

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        webView = new WebView(this);
        setContentView(webView);
        webView.setOnApplyWindowInsetsListener((View v, WindowInsets insets) -> {
            int top = insets.getSystemWindowInsetTop();
            v.setPadding(0, top, 0, 0);
            return insets;
        });
        webView.requestApplyInsets();
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        webView.addJavascriptInterface(new NativeBridge(this), "NativeBridge");
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient(){
            @Override public void onPermissionRequest(PermissionRequest r){
                runOnUiThread(() -> {
                    if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) r.grant(r.getResources());
                    else { pendingWebPermission=r; requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA); }
                });
            }
            @Override public boolean onShowFileChooser(WebView w, ValueCallback<Uri[]> cb, FileChooserParams p){
                if(fileCallback!=null) fileCallback.onReceiveValue(null);
                fileCallback=cb;
                String accept="*/*";
                if(p.getAcceptTypes()!=null) for(String t:p.getAcceptTypes()) if(t!=null && t.contains("/")){ accept=t; break; }
                Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType(accept);
                Intent chooser=Intent.createChooser(pick,"Scegli file");
                if(accept.startsWith("image/") || "*/*".equals(accept)){
                    try {
                        android.content.ContentValues cv=new android.content.ContentValues();
                        cv.put(MediaStore.Images.Media.DISPLAY_NAME,"officina_photo_"+System.currentTimeMillis()+".jpg");
                        cv.put(MediaStore.Images.Media.MIME_TYPE,"image/jpeg");
                        pendingCameraUri=getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,cv);
                        Intent cam=new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                        cam.putExtra(MediaStore.EXTRA_OUTPUT,pendingCameraUri);
                        cam.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS,new Intent[]{cam});
                    } catch(Exception ignored){}
                }
                startActivityForResult(chooser,REQ_FILE);
                return true;
            }
        });
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
        webView.loadUrl("file:///android_asset/index.html");
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==REQ_FILE && fileCallback!=null){
            Uri[] out=null;
            if(resultCode==RESULT_OK){
                if(data!=null && data.getData()!=null) out=new Uri[]{data.getData()};
                else if(pendingCameraUri!=null) out=new Uri[]{pendingCameraUri};
            }
            fileCallback.onReceiveValue(out);
            fileCallback=null;
            pendingCameraUri=null;
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] results){
        super.onRequestPermissionsResult(requestCode,permissions,results);
        if(requestCode==REQ_CAMERA && pendingWebPermission!=null){
            if(results.length>0 && results[0]==PackageManager.PERMISSION_GRANTED) pendingWebPermission.grant(pendingWebPermission.getResources());
            else pendingWebPermission.deny();
            pendingWebPermission=null;
        }
    }

    @Override public void onBackPressed(){
        if(webView!=null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
