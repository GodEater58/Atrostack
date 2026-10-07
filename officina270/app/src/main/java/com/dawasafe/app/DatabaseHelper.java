package com.dawasafe.app;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import android.util.Base64;
import org.json.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

public class DatabaseHelper extends SQLiteOpenHelper {
    private final Context ctx;
    DatabaseHelper(Context c){ super(c,"officina_stock.db",null,1); ctx=c.getApplicationContext(); }

    @Override public void onCreate(SQLiteDatabase db){
        db.execSQL("CREATE TABLE metadata(k TEXT PRIMARY KEY,v TEXT NOT NULL)");
        db.execSQL("CREATE TABLE settings(id INTEGER PRIMARY KEY CHECK(id=1),json TEXT NOT NULL)");
        db.execSQL("CREATE TABLE locations(id TEXT PRIMARY KEY,site TEXT,code TEXT COLLATE NOCASE,json TEXT NOT NULL)");
        db.execSQL("CREATE TABLE items(id TEXT PRIMARY KEY,code TEXT COLLATE NOCASE,normalized_name TEXT,json TEXT NOT NULL,photo_path TEXT)");
        db.execSQL("CREATE UNIQUE INDEX idx_items_code ON items(code COLLATE NOCASE)");
        db.execSQL("CREATE INDEX idx_items_name ON items(normalized_name)");
        db.execSQL("CREATE TABLE movements(id TEXT PRIMARY KEY,item_id TEXT,at TEXT,type TEXT,json TEXT NOT NULL)");
        db.execSQL("CREATE INDEX idx_mov_item_at ON movements(item_id,at)");
        db.execSQL("CREATE TABLE loans(id TEXT PRIMARY KEY,item_id TEXT,active INTEGER,json TEXT NOT NULL)");
        db.execSQL("CREATE INDEX idx_loan_item_active ON loans(item_id,active)");
    }

    @Override public void onUpgrade(SQLiteDatabase db,int oldV,int newV){}

    boolean hasData(){
        try(Cursor c=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM items",null)){
            if(c.moveToFirst()&&c.getLong(0)>0)return true;
        }
        try(Cursor c=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM metadata WHERE k='initialized'",null)){
            return c.moveToFirst()&&c.getLong(0)>0;
        }
    }

    synchronized boolean saveState(String raw){
        SQLiteDatabase db=getWritableDatabase();
        db.beginTransaction();
        try{
            JSONObject s=new JSONObject(raw);
            ContentValues meta=new ContentValues();
            meta.put("k","version");
            meta.put("v",s.optString("version","2.7.0"));
            db.insertWithOnConflict("metadata",null,meta,SQLiteDatabase.CONFLICT_REPLACE);
            meta.clear();
            meta.put("k","initialized");
            meta.put("v","1");
            db.insertWithOnConflict("metadata",null,meta,SQLiteDatabase.CONFLICT_REPLACE);

            ContentValues set=new ContentValues();
            set.put("id",1);
            set.put("json",s.optJSONObject("settings")!=null?s.optJSONObject("settings").toString():"{}");
            db.insertWithOnConflict("settings",null,set,SQLiteDatabase.CONFLICT_REPLACE);

            syncLocations(db,s.optJSONArray("locations"));
            syncItems(db,s.optJSONArray("items"));
            syncMovements(db,s.optJSONArray("movements"));
            syncLoans(db,s.optJSONArray("loans"));
            db.setTransactionSuccessful();
            return true;
        }catch(Exception e){
            e.printStackTrace();
            return false;
        }finally{
            db.endTransaction();
        }
    }

    private void syncLocations(SQLiteDatabase db,JSONArray a)throws Exception{
        Set<String> keep=new HashSet<>();
        if(a==null)a=new JSONArray();
        for(int n=0;n<a.length();n++){
            JSONObject o=a.getJSONObject(n);
            String id=o.optString("id");
            if(id.isEmpty())continue;
            keep.add(id);
            ContentValues v=new ContentValues();
            v.put("id",id);
            v.put("site",o.optString("site"));
            v.put("code",o.optString("code"));
            v.put("json",o.toString());
            db.insertWithOnConflict("locations",null,v,SQLiteDatabase.CONFLICT_REPLACE);
        }
        deleteMissing(db,"locations",keep);
    }

    private void syncItems(SQLiteDatabase db,JSONArray a)throws Exception{
        Set<String> keep=new HashSet<>();
        if(a==null)a=new JSONArray();
        File dir=new File(ctx.getFilesDir(),"item_photos");
        if(!dir.exists())dir.mkdirs();

        for(int n=0;n<a.length();n++){
            JSONObject src=a.getJSONObject(n);
            JSONObject o=new JSONObject(src.toString());
            String id=o.optString("id");
            if(id.isEmpty())continue;
            keep.add(id);

            String photo=o.optString("photo","");
            String photoPath=existingPhotoPath(db,id);
            if(photo.startsWith("data:image/")){
                photoPath=storePhoto(dir,id,photo);
            }else if(photo.isEmpty()&&photoPath!=null){
                new File(photoPath).delete();
                photoPath=null;
            }

            o.put("photo","");
            ContentValues v=new ContentValues();
            v.put("id",id);
            v.put("code",o.optString("code"));
            v.put("normalized_name",normalize(o.optString("description")));
            v.put("json",o.toString());
            v.put("photo_path",photoPath);
            db.insertWithOnConflict("items",null,v,SQLiteDatabase.CONFLICT_REPLACE);
        }

        cleanupRemovedPhotos(db,keep);
        deleteMissing(db,"items",keep);
    }

    private void syncMovements(SQLiteDatabase db,JSONArray a)throws Exception{
        Set<String> keep=new HashSet<>();
        if(a==null)a=new JSONArray();
        for(int n=0;n<a.length();n++){
            JSONObject o=a.getJSONObject(n);
            String id=o.optString("id");
            if(id.isEmpty())continue;
            keep.add(id);
            ContentValues v=new ContentValues();
            v.put("id",id);
            v.put("item_id",o.optString("itemId"));
            v.put("at",o.optString("at"));
            v.put("type",o.optString("type"));
            v.put("json",o.toString());
            db.insertWithOnConflict("movements",null,v,SQLiteDatabase.CONFLICT_REPLACE);
        }
        deleteMissing(db,"movements",keep);
    }

    private void syncLoans(SQLiteDatabase db,JSONArray a)throws Exception{
        Set<String> keep=new HashSet<>();
        if(a==null)a=new JSONArray();
        for(int n=0;n<a.length();n++){
            JSONObject o=a.getJSONObject(n);
            String id=o.optString("id");
            if(id.isEmpty())continue;
            keep.add(id);
            ContentValues v=new ContentValues();
            v.put("id",id);
            v.put("item_id",o.optString("itemId"));
            v.put("active",o.optBoolean("active",true)?1:0);
            v.put("json",o.toString());
            db.insertWithOnConflict("loans",null,v,SQLiteDatabase.CONFLICT_REPLACE);
        }
        deleteMissing(db,"loans",keep);
    }

    private void deleteMissing(SQLiteDatabase db,String table,Set<String> keep){
        try(Cursor c=db.rawQuery("SELECT id FROM "+table,null)){
            while(c.moveToNext()){
                String id=c.getString(0);
                if(!keep.contains(id))db.delete(table,"id=?",new String[]{id});
            }
        }
    }

    private String existingPhotoPath(SQLiteDatabase db,String id){
        try(Cursor c=db.query("items",new String[]{"photo_path"},"id=?",new String[]{id},null,null,null)){
            return c.moveToFirst()?c.getString(0):null;
        }
    }

    private void cleanupRemovedPhotos(SQLiteDatabase db,Set<String> keep){
        try(Cursor c=db.query("items",new String[]{"id","photo_path"},null,null,null,null,null)){
            while(c.moveToNext()){
                if(!keep.contains(c.getString(0))&&c.getString(1)!=null)new File(c.getString(1)).delete();
            }
        }
    }

    private String storePhoto(File dir,String id,String dataUrl)throws Exception{
        int comma=dataUrl.indexOf(',');
        if(comma<0)return null;
        String head=dataUrl.substring(0,comma);
        String ext=head.contains("png")?"png":"jpg";
        byte[] bytes=Base64.decode(dataUrl.substring(comma+1),Base64.DEFAULT);
        String hash=hex(MessageDigest.getInstance("SHA-256").digest(bytes)).substring(0,16);
        File f=new File(dir,id+"_"+hash+"."+ext);
        if(!f.exists()){
            try(FileOutputStream out=new FileOutputStream(f)){out.write(bytes);}
        }
        File[] all=dir.listFiles();
        if(all!=null)for(File old:all)if(old.getName().startsWith(id+"_")&&!old.equals(f))old.delete();
        return f.getAbsolutePath();
    }

    private static String hex(byte[] b){
        StringBuilder s=new StringBuilder();
        for(byte x:b)s.append(String.format(Locale.US,"%02x",x));
        return s.toString();
    }

    private static String normalize(String s){
        return java.text.Normalizer.normalize(s==null?"":s,java.text.Normalizer.Form.NFD)
                .replaceAll("\\p{M}+","")
                .toLowerCase(Locale.ROOT)
                .trim()
                .replaceAll("\\s+"," ");
    }

    synchronized String loadState(){
        SQLiteDatabase db=getReadableDatabase();
        JSONObject s=new JSONObject();
        try{
            String ver="2.7.0";
            try(Cursor c=db.rawQuery("SELECT v FROM metadata WHERE k='version'",null)){
                if(c.moveToFirst())ver=c.getString(0);
            }
            s.put("version",ver);
            try(Cursor c=db.rawQuery("SELECT json FROM settings WHERE id=1",null)){
                s.put("settings",c.moveToFirst()?new JSONObject(c.getString(0)):new JSONObject());
            }
            s.put("locations",readJsonArray(db,"SELECT json FROM locations ORDER BY rowid",false));
            s.put("items",readJsonArray(db,"SELECT json,photo_path FROM items ORDER BY rowid",true));
            s.put("movements",readJsonArray(db,"SELECT json FROM movements ORDER BY rowid",false));
            s.put("loans",readJsonArray(db,"SELECT json FROM loans ORDER BY rowid",false));
            return s.toString();
        }catch(Exception e){
            e.printStackTrace();
            return "";
        }
    }

    private JSONArray readJsonArray(SQLiteDatabase db,String sql,boolean photo)throws Exception{
        JSONArray a=new JSONArray();
        try(Cursor c=db.rawQuery(sql,null)){
            while(c.moveToNext()){
                JSONObject o=new JSONObject(c.getString(0));
                if(photo){
                    String path=c.getString(1);
                    o.put("photo",path==null?"":toDataUrl(path));
                }
                a.put(o);
            }
        }
        return a;
    }

    private String toDataUrl(String path){
        try{
            File f=new File(path);
            if(!f.exists())return "";
            byte[] bytes=new byte[(int)f.length()];
            try(FileInputStream in=new FileInputStream(f)){
                int off=0,n;
                while(off<bytes.length&&(n=in.read(bytes,off,bytes.length-off))>0)off+=n;
            }
            String mime=path.endsWith(".png")?"image/png":"image/jpeg";
            return "data:"+mime+";base64,"+Base64.encodeToString(bytes,Base64.NO_WRAP);
        }catch(Exception e){
            return "";
        }
    }
}
