package com.dawasafe.app;

import android.content.*;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.JavascriptInterface;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import javax.crypto.*;
import javax.crypto.spec.*;
import javax.crypto.SecretKeyFactory;

public class NativeBridge {
    private final Context ctx;
    private final DatabaseHelper db;
    private final SecureRandom rng=new SecureRandom();

    NativeBridge(Context c){
        ctx=c.getApplicationContext();
        db=new DatabaseHelper(ctx);
    }

    @JavascriptInterface public String loadState(String legacyJson){
        try{
            if(!db.hasData()&&legacyJson!=null&&!legacyJson.trim().isEmpty()){
                new JSONObject(legacyJson);
                if(!db.saveState(legacyJson))return legacyJson;
            }
            return db.hasData()?db.loadState():"";
        }catch(Exception e){
            return legacyJson==null?"":legacyJson;
        }
    }

    @JavascriptInterface public boolean saveState(String json){
        return db.saveState(json);
    }

    @JavascriptInterface public String exportEncryptedBackup(String json,String password){
        try{
            if(password==null||password.length()<8)return "Password troppo corta";
            String enc=encrypt(json,password);
            String name="OfficinaStock_backup_"+new java.text.SimpleDateFormat("yyyy-MM-dd",java.util.Locale.US).format(new java.util.Date())+".ostock";
            savePublic(name,"application/octet-stream",enc.getBytes(StandardCharsets.UTF_8));
            return "Backup cifrato salvato in Download: "+name;
        }catch(Exception e){
            e.printStackTrace();
            return "Errore backup: "+e.getMessage();
        }
    }

    @JavascriptInterface public String decryptBackup(String envelope,String password){
        try{
            return decrypt(envelope,password);
        }catch(Exception e){
            return "ERR:"+e.getClass().getSimpleName();
        }
    }

    @JavascriptInterface public String saveTextFile(String name,String mime,String text){
        try{
            savePublic(name,mime,text.getBytes(StandardCharsets.UTF_8));
            return "File salvato in Download: "+name;
        }catch(Exception e){
            return "Errore esportazione: "+e.getMessage();
        }
    }

    private String encrypt(String plain,String password)throws Exception{
        byte[] salt=new byte[16],iv=new byte[12];
        rng.nextBytes(salt);
        rng.nextBytes(iv);
        SecretKey key=derive(password,salt);
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.ENCRYPT_MODE,key,new GCMParameterSpec(128,iv));
        byte[] ct=c.doFinal(plain.getBytes(StandardCharsets.UTF_8));
        JSONObject o=new JSONObject();
        o.put("format","OFFICINA_STOCK_ENCRYPTED");
        o.put("version",1);
        o.put("cipher","AES-256-GCM");
        o.put("kdf","PBKDF2WithHmacSHA256");
        o.put("iterations",210000);
        o.put("salt",android.util.Base64.encodeToString(salt,android.util.Base64.NO_WRAP));
        o.put("iv",android.util.Base64.encodeToString(iv,android.util.Base64.NO_WRAP));
        o.put("ciphertext",android.util.Base64.encodeToString(ct,android.util.Base64.NO_WRAP));
        return o.toString();
    }

    private String decrypt(String envelope,String password)throws Exception{
        JSONObject o=new JSONObject(envelope);
        if(!"OFFICINA_STOCK_ENCRYPTED".equals(o.optString("format")))throw new IllegalArgumentException("format");
        byte[] salt=android.util.Base64.decode(o.getString("salt"),android.util.Base64.DEFAULT);
        byte[] iv=android.util.Base64.decode(o.getString("iv"),android.util.Base64.DEFAULT);
        byte[] ct=android.util.Base64.decode(o.getString("ciphertext"),android.util.Base64.DEFAULT);
        SecretKey key=derive(password,salt);
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,iv));
        return new String(c.doFinal(ct),StandardCharsets.UTF_8);
    }

    private SecretKey derive(String pwd,byte[] salt)throws Exception{
        PBEKeySpec spec=new PBEKeySpec(pwd.toCharArray(),salt,210000,256);
        byte[] k=SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded();
        spec.clearPassword();
        return new SecretKeySpec(k,"AES");
    }

    private void savePublic(String name,String mime,byte[] bytes)throws Exception{
        if(Build.VERSION.SDK_INT>=29){
            ContentValues v=new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME,name);
            v.put(MediaStore.Downloads.MIME_TYPE,mime);
            v.put(MediaStore.Downloads.RELATIVE_PATH,Environment.DIRECTORY_DOWNLOADS+"/OfficinaStock");
            android.net.Uri u=ctx.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,v);
            if(u==null)throw new IOException("Impossibile creare file");
            try(OutputStream out=ctx.getContentResolver().openOutputStream(u)){
                if(out==null)throw new IOException("Output non disponibile");
                out.write(bytes);
            }
        }else{
            File dir=Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            if(!dir.exists())dir.mkdirs();
            try(FileOutputStream out=new FileOutputStream(new File(dir,name))){
                out.write(bytes);
            }
        }
    }
}
