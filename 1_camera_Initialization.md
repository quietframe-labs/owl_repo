### build in layers
# Step 1: Future Network architecture
Camera → Network → Pi → Video stream → Recording → Detection → Web UI

                 Internet
                    │
              Home Router
                    │
              Ethernet/Wi-Fi
                    │
             Raspberry Pi 4
                    │
          ┌─────────┴─────────┐
          │ Security Network  │
          │   192.168.50.x    │
          └─────────┬─────────┘
                    │ Wi-Fi
                    │
              Tapo Camera

# Step 2: Enable the camera's local stream
### enable RTSP/ONVIF access and create camera account
    Conceptually: rtsp://CAMERA_IP:554/stream1
typically:
    stream1 = main/high-quality stream
    stream2 = lower-resolution stream

# Step 3: Install only the basic video tools
### install ffmpeg, a command-line program for working with video and audio
    sudo apt update
    sudo apt install ffmpeg
 Verify
    ffmpeg -version
# Step 3.5: initialize camera on same wifi as raspberry pie
### currently using tapo C101 wifi camera
i/tapo app:
Create camera account in advanced settings
Change ip address to static and record

# Step 4: Find the camera
### On the pi:
    ping -c 4 192.168.1.50
    ip neigh show 192.168.1.50

# Step 4.5: Check RTSP port 554
On the pi:
    nc -zv 192.168.1.50 554
#if nc isn't installed: 
    sudo apt install netcat-openbsd -y
Successful result:
    Connection to 192.168.1.50 554 port [tcp/rtsp] succeeded!

Step 5: Test actual camera stream
On the pi:
    ffmpeg -rtsp_transport tcp \
    -i "rtsp://CaptainOwl:YOUR_PASSWORD@192.168.1.50:554/stream1" \
    -t 10 \
    -map 0:v:0 \
    -c:v copy \
    -an \
    test.mp4

#-map 0:v:0    use the first video stream
#-c:v copy     don't re-encode the video
#-an           ignore audio
#~test.mp4 should create 10-second video, no audio.

Step 5.5: Verify download
On PC: Download test.mp4
    scp admin@192.168.1.49:/home/admin/test.mp4 "$env:USERPROFILE\Downloads\test.mp4"