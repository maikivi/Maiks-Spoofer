-- Maik's Spoofer Plugin
-- Place in Roblox Plugins folder

local HttpService = game:GetService("HttpService")
local StarterGui = game:GetService("StarterGui")
local TweenService = game:GetService("TweenService")
local port = 5555
local baseUrl = "http://localhost:"
local busy = false

local colors = {
    background = Color3.fromRGB(15, 18, 24),
    panel = Color3.fromRGB(23, 27, 35),
    panelAlt = Color3.fromRGB(29, 34, 44),
    border = Color3.fromRGB(52, 61, 76),
    text = Color3.fromRGB(240, 244, 250),
    muted = Color3.fromRGB(148, 158, 175),
    accent = Color3.fromRGB(83, 156, 255),
    accentDark = Color3.fromRGB(47, 99, 181),
    success = Color3.fromRGB(49, 205, 126),
}

local toolbar = plugin:CreateToolbar("Maik")
local btn = toolbar:CreateButton("Spoofer", "Animation Spoofer", "")

local wi = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Float, false, false, 340, 390, 300, 340)
local gui = plugin:CreateDockWidgetPluginGui("MaikGUI", wi)
gui.Title = "Maik's Spoofer"

local m = Instance.new("Frame")
m.Size = UDim2.new(1, 0, 1, 0)
m.BackgroundColor3 = colors.background
m.BorderSizePixel = 0
m.Parent = gui

local h = Instance.new("Frame")
h.Size = UDim2.new(1, 0, 0, 74)
h.BackgroundColor3 = colors.panel
h.BorderSizePixel = 0
h.Parent = m

local t = Instance.new("TextLabel")
t.Text = "MAIK'S SPOOFER"
t.Size = UDim2.new(1, -40, 0, 24)
t.Position = UDim2.new(0, 20, 0, 13)
t.TextColor3 = colors.text
t.BackgroundTransparency = 1
t.TextSize = 16
t.Font = Enum.Font.GothamBold
t.TextXAlignment = Enum.TextXAlignment.Left
t.Parent = h

local subtitle = Instance.new("TextLabel")
subtitle.Text = "Animation replacement utility"
subtitle.Size = UDim2.new(1, -40, 0, 18)
subtitle.Position = UDim2.new(0, 20, 0, 39)
subtitle.TextColor3 = colors.muted
subtitle.BackgroundTransparency = 1
subtitle.TextSize = 10
subtitle.Font = Enum.Font.Gotham
subtitle.TextXAlignment = Enum.TextXAlignment.Left
subtitle.Parent = h

local c = Instance.new("Frame")
c.Size = UDim2.new(1, -32, 1, -90)
c.Position = UDim2.new(0, 16, 0, 86)
c.BackgroundTransparency = 1
c.Parent = m

local function addCorner(instance, radius)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, radius)
    corner.Parent = instance
end

local function addStroke(instance, color)
    local stroke = Instance.new("UIStroke")
    stroke.Color = color
    stroke.Transparency = 0.2
    stroke.Thickness = 1
    stroke.Parent = instance
end

local section = Instance.new("TextLabel")
section.Text = "CONNECTION"
section.Size = UDim2.new(1, 0, 0, 16)
section.TextColor3 = colors.muted
section.BackgroundTransparency = 1
section.TextSize = 10
section.Font = Enum.Font.GothamBold
section.TextXAlignment = Enum.TextXAlignment.Left
section.Parent = c

local connection = Instance.new("Frame")
connection.Size = UDim2.new(1, 0, 0, 48)
connection.Position = UDim2.new(0, 0, 0, 21)
connection.BackgroundColor3 = colors.panel
connection.BorderSizePixel = 0
connection.Parent = c
addCorner(connection, 7)
addStroke(connection, colors.border)

local pl = Instance.new("TextLabel")
pl.Text = "PORT"
pl.Size = UDim2.new(0, 38, 1, 0)
pl.Position = UDim2.new(0, 14, 0, 0)
pl.TextColor3 = colors.muted
pl.BackgroundTransparency = 1
pl.TextSize = 10
pl.Font = Enum.Font.GothamBold
pl.TextXAlignment = Enum.TextXAlignment.Left
pl.Parent = connection

local pb = Instance.new("TextBox")
pb.Text = "5555"
pb.Size = UDim2.new(0, 72, 0, 30)
pb.Position = UDim2.new(0, 57, 0.5, -15)
pb.BackgroundColor3 = colors.panelAlt
pb.TextColor3 = colors.text
pb.BorderSizePixel = 0
pb.TextSize = 12
pb.Font = Enum.Font.GothamMedium
pb.ClearTextOnFocus = false
pb.Parent = connection
addCorner(pb, 5)
addStroke(pb, colors.border)

local endpoint = Instance.new("TextLabel")
endpoint.Text = "localhost"
endpoint.Size = UDim2.new(1, -145, 1, 0)
endpoint.Position = UDim2.new(0, 140, 0, 0)
endpoint.TextColor3 = colors.muted
endpoint.BackgroundTransparency = 1
endpoint.TextSize = 10
endpoint.Font = Enum.Font.Gotham
endpoint.TextXAlignment = Enum.TextXAlignment.Right
endpoint.Parent = connection

local actions = Instance.new("Frame")
actions.Size = UDim2.new(1, 0, 0, 38)
actions.Position = UDim2.new(0, 0, 0, 80)
actions.BackgroundTransparency = 1
actions.Parent = c

local cn = Instance.new("TextButton")
cn.Text = "CONNECT"
cn.Size = UDim2.new(0.48, 0, 1, 0)
cn.BackgroundColor3 = colors.accentDark
cn.TextColor3 = colors.text
cn.BorderSizePixel = 0
cn.TextSize = 11
cn.Font = Enum.Font.GothamBold
cn.AutoButtonColor = false
cn.Parent = actions
addCorner(cn, 6)

local sp = Instance.new("TextButton")
sp.Text = "SPOOF"
sp.Size = UDim2.new(0.48, 0, 1, 0)
sp.Position = UDim2.new(0.52, 0, 0, 0)
sp.BackgroundColor3 = colors.success
sp.TextColor3 = Color3.fromRGB(8, 25, 18)
sp.BorderSizePixel = 0
sp.TextSize = 11
sp.Font = Enum.Font.GothamBold
sp.AutoButtonColor = false
sp.Parent = actions
addCorner(sp, 6)

local function setButtonHover(button, baseColor, hoverColor)
    button.MouseEnter:Connect(function()
        TweenService:Create(button, TweenInfo.new(0.12), {BackgroundColor3 = hoverColor}):Play()
    end)
    button.MouseLeave:Connect(function()
        TweenService:Create(button, TweenInfo.new(0.12), {BackgroundColor3 = baseColor}):Play()
    end)
end

setButtonHover(cn, colors.accentDark, colors.accent)
setButtonHover(sp, colors.success, Color3.fromRGB(73, 228, 148))

local statusTitle = Instance.new("TextLabel")
statusTitle.Text = "ACTIVITY"
statusTitle.Size = UDim2.new(1, 0, 0, 16)
statusTitle.Position = UDim2.new(0, 0, 0, 133)
statusTitle.TextColor3 = colors.muted
statusTitle.BackgroundTransparency = 1
statusTitle.TextSize = 10
statusTitle.Font = Enum.Font.GothamBold
statusTitle.TextXAlignment = Enum.TextXAlignment.Left
statusTitle.Parent = c

local st = Instance.new("Frame")
st.Size = UDim2.new(1, 0, 0, 44)
st.Position = UDim2.new(0, 0, 0, 155)
st.BackgroundColor3 = colors.panel
st.BorderSizePixel = 0
st.Parent = c
addCorner(st, 7)
addStroke(st, colors.border)

local sl = Instance.new("TextLabel")
sl.Text = "READY"
sl.Size = UDim2.new(1, -28, 1, 0)
sl.Position = UDim2.new(0, 14, 0, 0)
sl.TextColor3 = colors.muted
sl.BackgroundTransparency = 1
sl.TextSize = 11
sl.Font = Enum.Font.GothamBold
sl.TextXAlignment = Enum.TextXAlignment.Left
sl.Parent = st

local pf = Instance.new("Frame")
pf.Size = UDim2.new(1, 0, 0, 2)
pf.Position = UDim2.new(0, 0, 1, -2)
pf.BackgroundColor3 = colors.border
pf.BorderSizePixel = 0
pf.Visible = false
pf.Parent = st

local pb2 = Instance.new("Frame")
pb2.Size = UDim2.new(0, 0, 1, 0)
pb2.BackgroundColor3 = colors.accent
pb2.BorderSizePixel = 0
pb2.Parent = pf

local ll = Instance.new("TextLabel")
ll.Text = ""
ll.Size = UDim2.new(1, 0, 0, 40)
ll.Position = UDim2.new(0, 0, 0, 207)
ll.TextColor3 = colors.muted
ll.BackgroundTransparency = 1
ll.TextSize = 10
ll.Font = Enum.Font.Gotham
ll.TextXAlignment = Enum.TextXAlignment.Left
ll.TextYAlignment = Enum.TextYAlignment.Top
ll.TextWrapped = true
ll.Parent = c

local function up()
    local p = tonumber(pb.Text)
    if p and p >= 1 and p <= 65535 and p % 1 == 0 then
        port = p
        pb.Text = tostring(p)
        return true
    end
    pb.Text = tostring(port)
    return false
end

local function decode(response)
    local ok, data = pcall(function()
        return HttpService:JSONDecode(response)
    end)
    if ok and type(data) == "table" then
        return data
    end
    return nil
end

pb.FocusLost:Connect(up)

cn.MouseButton1Click:Connect(function()
    up()
    sl.Text = "CONNECTING..."
    sl.TextColor3 = Color3.fromRGB(255, 170, 0)
    local ok, res = pcall(function()
        return HttpService:GetAsync(baseUrl .. port .. "/status")
    end)
    if ok then
        local data = decode(res)
        if data and data.status == "online" then
            sl.Text = "CONNECTED"
            sl.TextColor3 = Color3.fromRGB(0, 255, 120)
            ll.Text = "Ready to spoof!"
        else
            sl.Text = "INVALID RESPONSE"
            sl.TextColor3 = Color3.fromRGB(255, 130, 0)
            ll.Text = "The local service returned an invalid response."
        end
    else
        sl.Text = "OFFLINE"
        sl.TextColor3 = Color3.fromRGB(255, 60, 60)
        ll.Text = "Start Maik's Spoofer first!"
    end
end)

sp.MouseButton1Click:Connect(function()
    if busy then
        return
    end
    up()
    busy = true
    sl.Text = "SCANNING..."
    sl.TextColor3 = Color3.fromRGB(255, 170, 0)
    pf.Visible = true
    pb2.Size = UDim2.new(0.1, 0, 1, 0)
    
    local ids = {}
    local anms = {}
    
    local function sc(x)
        if not x then return end
        pcall(function()
            for _, o in ipairs(x:GetDescendants()) do
                if o:IsA("Animation") then
                    local n = string.match(o.AnimationId, "%d+")
                    if n and tonumber(n) > 0 then
                        table.insert(anms, o)
                        if not table.find(ids, tonumber(n)) then
                            table.insert(ids, tonumber(n))
                        end
                    end
                end
            end
        end)
    end
    
    sc(game:GetService("Workspace"))
    sc(game:GetService("ReplicatedStorage"))
    sc(game:GetService("ServerStorage"))
    sc(game:GetService("StarterPlayer"))
    sc(game:GetService("ServerScriptService"))
    sc(game:GetService("Lighting"))
    
    pb2.Size = UDim2.new(0.3, 0, 1, 0)
    
    if #ids == 0 then
        sl.Text = "NONE FOUND"
        sl.TextColor3 = Color3.fromRGB(255, 130, 0)
        ll.Text = "No animations in this game!"
        pf.Visible = false
        busy = false
        return
    end
    
    ll.Text = "Found " .. #ids .. " animations..."
    sl.Text = "SPOOFING..."
    sl.TextColor3 = Color3.fromRGB(0, 170, 255)
    pb2.Size = UDim2.new(0.5, 0, 1, 0)
    
    local ok, res = pcall(function()
        return HttpService:PostAsync(
            baseUrl .. port .. "/spoof",
            HttpService:JSONEncode({anim_ids = ids}),
            Enum.HttpContentType.ApplicationJson
        )
    end)
    
    if ok then
        local d = decode(res)
        
        if not d then
            sl.Text = "INVALID RESPONSE"
            sl.TextColor3 = Color3.fromRGB(255, 60, 60)
            ll.Text = "The local service returned invalid JSON."
            pf.Visible = false
            busy = false
            return
        end

        if d.error then
            sl.Text = "ERROR"
            sl.TextColor3 = Color3.fromRGB(255, 60, 60)
            ll.Text = d.error
            pf.Visible = false
            busy = false
            return
        end
        
        pb2.Size = UDim2.new(0.8, 0, 1, 0)
        local rp = 0
        
        for _, a in ipairs(anms) do
            local o = string.match(a.AnimationId, "%d+")
            if o and d[o] then
                a.AnimationId = "rbxassetid://" .. d[o]
                rp = rp + 1
            end
        end
        
        pb2.Size = UDim2.new(1, 0, 1, 0)
        sl.Text = "DONE"
        sl.TextColor3 = Color3.fromRGB(0, 255, 120)
        ll.Text = "Spoofed " .. rp .. "/" .. #ids .. "!"
        
        StarterGui:SetCore("SendNotification", {
            Title = "Maik's Spoofer",
            Text = "Spoofed " .. rp .. " animations!",
            Duration = 4
        })
    else
        sl.Text = "ERROR"
        sl.TextColor3 = Color3.fromRGB(255, 60, 60)
        ll.Text = tostring(res)
    end
    
    pf.Visible = false
    busy = false
end)

btn.Click:Connect(function()
    gui.Enabled = not gui.Enabled
end)
