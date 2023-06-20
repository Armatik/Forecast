import requests
from datetime import datetime
import gi
import time
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw

meteo = None
forecast = None
settings = Gio.Settings.new("dev.salaniLeo.forecast")
main_window = None
saved_locations = settings.get_strv('wthr-locs')
use_glassy = settings.get_boolean('use-glassy')

app = None

both_update = True #TODO

lat = None
lon = None

conditions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
text_label = Gtk.Label()
info_label = Gtk.Label()

title_label = Gtk.Label()
subtitle_label = Gtk.Label()
local_tm_label = Gtk.Label()

situa_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
situa_img = Gtk.Image()

hourly_forecast_box = Gtk.Box(spacing=0, orientation=Gtk.Orientation.HORIZONTAL)
daily_forecast_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

icon_loc = None

today = datetime.now()

degrees_unit = None
speed_unit = None
units = settings.get_string('units').split(' ')[0].lower()
raw_units = settings.get_string('units')
degrees_unit = raw_units[raw_units.find(",")+1:raw_units.find("-")]
speed_unit   = raw_units[raw_units.find("-")+1:]

last_refresh = 0

class main_page(Gtk.Box):
    def __init__(self, thread, window, name, flatpak):
        super().__init__()

        global icon_loc, meteo, lat, lon

        if name is not None:
            text_raw = name.split(" - ")[1]
        else:
            text_raw = saved_locations[0]

        if flatpak:
            icon_loc = '/app/share/icons/hicolor/scalable/status/'
        # elif appimage:
        #     icon_loc.load_from_path('style.css')
        else:
            icon_loc = 'data/status/'

        # extracts the coordinates from saved locations
        coords_raw = text_raw[text_raw.find("(")+1:text_raw.find(")")]
            
        lat = coords_raw.split("; ")[0]
        lon = coords_raw.split("; ")[1]

        # gets weather from api
        meteo = get_wttr(lat, lon)

        # sets main_window to windo
        global main_window
        main_window = window
        global app
        app = self

        # sets properties for current situa
        global title_label
        title_label.set_justify(Gtk.Justification.LEFT)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_valign(Gtk.Align.START)
        title_label.set_css_classes(['text_big'])
        
        # sets properties for temperature
        global subtitle_label
        subtitle_label.set_justify(Gtk.Justification.LEFT)
        subtitle_label.set_halign(Gtk.Align.START)
        subtitle_label.set_valign(Gtk.Align.START)
        subtitle_label.set_css_classes(['text_medium'])

        # sets properties for local time
        global local_tm_label
        local_tm_label.set_halign(Gtk.Align.START)
        local_tm_label.set_valign(Gtk.Align.START)

        # adds properties for conditions box
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title_box.append(title_label)
        title_box.append(subtitle_label)
        title_box.append(local_tm_label)
        title_box.set_size_request(200, -1)
        title_box.set_halign(Gtk.Align.END)
        title_box.set_valign(Gtk.Align.CENTER)

        # sets properties for the current situa icon
        global situa_box, situa_img
        situa_img.set_valign(Gtk.Align.CENTER)
        situa_img.set_halign(Gtk.Align.CENTER)
        
        # adds all the elements to current situa box
        situa_box.append(situa_img)
        situa_box.append(title_box)
        situa_box.set_size_request(300, 150)

        # creates the box to switch city
        window.saved_loc_box = Gtk.ComboBoxText.new()

        # sets properties for the top-left current situa label
        global conditions_box
        conditions_box.set_halign(Gtk.Align.END)
        conditions_box.set_valign(Gtk.Align.CENTER)
        conditions_box.set_margin_top(24)
        conditions_box.set_margin_end(24)
        conditions_box.append(text_label)
        conditions_box.append(info_label)
        conditions_box.set_size_request(250, 175)

        # loads all saved locations
        load_locations(False, 0, window)

        # adds everything to headerbar
        window.header_bar.pack_start(window.saved_loc_box)
        window.header_bar.pack_start(window.refresh_button)
        window.header_bar.pack_end(window.menu_button)
        window.header_bar.pack_end(window.add_button)
        
        window.saved_loc_box.set_active(index_=0)

        # ------ 3 hours forecast ------ #
        get_forecast(False)

        self.right_box = Gtk.Box()
        self.inner_right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # creates a scroll window to store 3 hour forecast
        self.next_hours_scroll = Gtk.ScrolledWindow()
        self.next_hours_scroll.set_child(hourly_forecast_box)
        self.next_hours_scroll.set_valign(Gtk.Align.CENTER)
        self.next_hours_scroll.set_vexpand(True)
        self.next_hours_scroll.set_hexpand(True)
        self.next_hours_scroll.set_valign(Gtk.Align.END)
        self.next_hours_scroll.set_min_content_height(150)
        
        # creates a sub box for the right box
        self.inner_right_box.append(get_info(meteo))
        self.inner_right_box.set_hexpand(True)

        # creates the right box
        self.right_box.append(self.inner_right_box)
        self.right_box.set_hexpand(True)

        # next 5 days forecast
        self.days_situa_box = Gtk.Box()
        self.days_situa_box.append(daily_forecast_box)
        self.days_situa_box.set_halign(Gtk.Align.START)

        # current weather situa icon and label
        self.left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.left_box.append(set_icon(window, meteo, False))
        self.left_box.append(self.days_situa_box)

        self.top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.top_box.append(self.left_box)
        self.top_box.append(self.right_box)

        # main page properties
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_end(6)
        self.set_margin_start(6)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_hexpand(True)

        self.append(self.top_box)
        self.append(self.next_hours_scroll)

        if settings.get_boolean("enhance-contrast"):
            style.apply_enhanced_text(None, True)
        if settings.get_boolean('use-glassy'):
            style.apply_glassy(None, True)

        # adds itself to stack
        window.stack.add_child(self)
        if saved_locations is not None:
            window.stack.set_visible_child(self)

        window.saved_loc_box.connect('changed', switch_city)

    # ---- function to refresh weather and change city ---- #
    def refresh(lati, longi, change_units):
        global meteo, lat, lon, last_refresh, app

        current_time = time.time()

        if change_units == 'True':
            global degrees_unit
            global speed_unit
            global units

            raw_units = settings.get_string('units')
            degrees_unit = raw_units[raw_units.find(",")+1:raw_units.find("-")]
            speed_unit   = raw_units[raw_units.find("-")+1:]
            units = raw_units.split(' ')[0].lower()

        # -- checks if new city coords are being added to list -- #
        if lati == None:
            if change_units:
                meteo = get_wttr(lat, lon) # requests newer data to apis
            else:
                if current_time - last_refresh >= 60:
                    last_refresh = current_time
                    meteo = get_wttr(lat, lon) # requests newer data to apis
                    get_forecast(True)
                else:
                    wait_toast = Adw.Toast.new(_('You must wait at least one minute to refresh'))
                    main_window.toast_overlay.add_toast(wait_toast)
        # -- if new city is being added -- #
        else:
            lat = lati  # updates global variables to new ones
            lon = longi #

            meteo = get_wttr(lati, longi) # requests new city weather
            get_forecast(True)

        get_info(meteo) # updates labels to new city weather
        set_icon(main_window, meteo, False) # updates icon to new city weather


    # ---- box used to fill blanc spaces ---- #
    def wttr_fill(self):
        wttr_fill = Gtk.Box()
        wttr_fill.set_hexpand(True)
        wttr_fill.set_vexpand(False)
        return wttr_fill

# ---- updates cities inside combo box ---- #
def load_locations(remove, active, window):
    if window is not None:
        global main_window
        main_window = window

    if remove:
        main_window.saved_loc_box.remove_all()
    for text in saved_locations:
        main_window.saved_loc_box.append_text(text=str(text.rsplit(" - ",1)[0]))
    main_window.saved_loc_box.set_active(index_=active)

# ---- sorts icons based on if it's the forecast or now ---- #
def set_icon(window, meteo, forecast):

        # checks if forecast is being requested 
        if not forecast:

            local_time  = str(convert_time(meteo['timezone']))
            name = meteo['name']                               #
            sky_value = meteo['weather'][0]['id']     #
            icon = meteo['weather'][0]['icon']                 # gets weather conditions
            situa = meteo['weather'][0]['id']                  #
            temp = int(meteo['main']['temp'])             #

            window.set_title(name + ' - ' + style.get_wttr_description(situa)) # updates window title to current weather conditions

            # --- adds image for current weather ---- #
            style.forecast_icon(icon, 100, False)

            # ---- label for current weather info ---- #
            global title_label
            title_label.set_label(style.get_wttr_description(situa))

            global subtitle_label
            subtitle_label.set_label(str(temp) + degrees_unit + '\n')

            global local_tm_label
            local_tm_label.set_label(_('Local time: ') + local_time)

            # --- applies gradient background if wanted --- #
            if settings.get_boolean('gradient-bg'):
                style.apply_bg(None, True)

        return situa_box


# ---- weather api call ---- #
def get_wttr(lat, lon):
    response = requests.get("http://api.openweathermap.org/data/2.5/weather?lat="+ lat +"&lon="+ lon +"&units="+ units +"&appid=" + settings.get_string('api-key-s'))
    return response.json()

# ---- forecast api call ---- # 
def get_frcst():
    response = requests.get("http://api.openweathermap.org/data/2.5/forecast?lat="+ lat +"&lon="+ lon +"&units="+ units +"&appid=" + settings.get_string('api-key-s'))
    return response.json()

# --- converts wind degrees to direction --- #
def wind_dir(angle):
        directions = [
            _("N"), _("NNE"), _("NE"), _("ENE"), _("E"), _("ESE"), _("SE"), _("SSE"),
            _("S"), _("SSW"), _("SW"), _("WSW"), _("W"), _("WNW"), _("NW"), _("NNW"),
        ]
        index = round(angle / (360.0 / len(directions))) % len(directions)
        return directions[index]

# ----- gets all the info for the bottom label ----- #
def get_info(meteo):

    global conditions_box
    global text_label
    global info_label

    # --- gets info from api response --- #
    feels_like  = str(round(meteo['main']['feels_like'], 1)) + degrees_unit
    humidity    = str(meteo["main"]["humidity"])   + "%    "
    wind_speed  = str(meteo['wind']['speed'])      + speed_unit +' '+ wind_dir(meteo['wind']['deg'])
    pressure    = str(meteo['main']['pressure'])   + ' hPa    '
    last_update = str(datetime.now().strftime("%H:%M"))

    try:
        wind_gusts  = str(meteo['wind']['gust']) + speed_unit
        if wind_gusts == '0' + speed_unit:
            wind_gusts = '...'
    except:
        wind_gusts  = '...'

    text_label.set_valign(Gtk.Align.CENTER)
    text_label.set_halign(Gtk.Align.CENTER)
    text_label.set_margin_start(24)
    text_label.set_markup(
        _("Last update") + '\n\n' +
        _("Feels like") + '\n' +
        _("Wind") + '\n' +
        _("Gusts") + '\n' +
        _("Pressure") + '\n' +
        _("Humidity") + '\n'
    )

    info_label.set_valign(Gtk.Align.CENTER)
    info_label.set_halign(Gtk.Align.CENTER)
    info_label.set_markup(
        last_update + '\n\n' +
        feels_like + '\n' +
        wind_speed + '\n' +
        wind_gusts + '\n' +
        pressure + '\n' +
        humidity + '\n' 
    )

    return conditions_box

def create_info_box(text, data, icon):
    box = Gtk.Box(spacing=3)
    label = Gtk.Label()
    if icon != None:
        icon = style.get_icon(meteo, 20, icon)
        box.append(icon)

    if text == None:
        if '°' in data:
            label.set_css_classes(['text_medium'])
        if icon != None:
            icon.set_css_classes(['icon_light'])
        label.set_label(data)
    else:
        label.set_label(text + data)

    box.append(label)
    box.set_halign(Gtk.Align.CENTER)
    return box

# --- sets up forecast --- #
def get_forecast(refresh):
    global forecast
    global hourly_forecast_box
    global daily_forecast_box

    forecast = get_frcst() # calls api to get forecast

    daily_forecast_box.set_halign(Gtk.Align.END)
    daily_forecast_box.set_valign(Gtk.Align.END)

    hourly_forecast_box.set_halign(Gtk.Align.CENTER)
    hourly_forecast_box.set_valign(Gtk.Align.CENTER)

    hours = 3
    day = 0

    min_temp = forecast["list"][0]['main']['temp']
    max_temp = forecast["list"][0]['main']['temp']
    min_temps = []
    max_temps = []

    # adds everything related to the api response to the app
    for weather in forecast["list"]:

        # declares the temperature for every 3 hour interval
        temperature = weather['main']['temp']
        wind_speed  = str(weather['wind']['speed']) + speed_unit

        # adds 24h forecast per 3 hours intervals
        if hours <= 21:

            hourly_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            
            local_time = int(convert_time(forecast["city"]["timezone"])[:2]) + hours  # gets local city time

            if local_time >= 24: # checks if local_time is more than 24
                local_time = local_time - 24
                if local_time < 10: # checks if local_time is less than 10
                    local_time = '0' + str(local_time) # adds a zero to time es. 1 -> 01
            local_time = str(local_time) + ':00' # adds minutes to time es. 01 -> 01:00

            hourly_box.append(Gtk.Label(label=local_time))    # Creates box for every 3 hours prevision
            hourly_box.append(style.get_icon(weather, 35, None))
            hourly_box.append(create_info_box(None, wind_speed, 'weather-windy-small.svg'))
            hourly_box.append(create_info_box(None, str(round(weather['main']['temp'], 1)) + '°', None))
            hourly_box.set_css_classes(['glassy'])

            if refresh:
                hourly_forecast_box.remove(hourly_forecast_box.get_first_child())

            hourly_forecast_box.append(hourly_box) # adds 3 hour interval to slider

        # checks the minimum temperature of the day
        if temperature < min_temp:
            min_temp = temperature

        # checks the maximum temperature of the day
        if temperature > max_temp:
            max_temp = temperature

        # saves both max and min temperatures of one day
        if hours % 24 == 0:
            min_temps.append(min_temp)
            max_temps.append(max_temp)

            if refresh:
                daily_forecast_box.remove(daily_forecast_box.get_first_child())

            # adds 5 days forecast
            daily_forecast_box.append(get_day_situa(weather, hours, int(min_temp), int(max_temp)))

            # resets min and max temperatures for the next day
            min_temp = temperature
            max_temp = temperature

            # counts the days
            day = day + 1

        hours = hours + 3

def get_day_situa(weather, hours, min_temp, max_temp):
    box = Gtk.Box(spacing=28)

    date_string = weather['dt_txt'][0:10]
    date = Gtk.Label()
    date.set_xalign(0)
    date.set_markup(datetime.strptime(date_string, "%Y-%m-%d").strftime("%A"))
    date.set_size_request(80, -1)

    wttr_date = weather["dt_txt"][8:10]

    box.append(date)
    box.append(style.get_icon(weather, 25, None))
    box.append(Gtk.Label(label=str(min_temp) + degrees_unit + '- ' + str(max_temp) + degrees_unit))

    return box
    
def switch_city(combobox):
    city = saved_locations[combobox.get_active()]

    if city is not None:
        coords_raw = city[city.find("(")+1:city.find(")")] # gets coords of new city
        lati = coords_raw.split("; ")[0]  # gets latitude of new city  
        longi = coords_raw.split("; ")[1] # gets longitude of new city

        main_page.refresh(lati, longi, len(saved_locations))
    
# ---- adds new city to cities list and calls each function to update weather and forecast based on new city ---- #
def add_city(city, window, first_time): 
    global saved_locations

    coords_raw = city[city.find("(")+1:city.find(")")] # gets coords of new city
    
    if len(coords_raw.split("; ")) == 2:
        
        if city in saved_locations: # skips city if already added
            # TODO
            None
        else:

            saved_locations.append(str(city))   # adds new city to cities list
            settings.set_strv('wthr-locs', saved_locations)  # updates gschema setting to contain new city
            
            if first_time:
                window.start_application()
            else:
                load_locations(True, len(saved_locations)-1, window)


# ---- funtction to get city based on user input ---- #
def get_cities(any, self, entry):

    # gets user input
    name = entry.get_text()
    
    # calls api to get cities
    response = requests.get("http://api.openweathermap.org/data/2.5/find?q="+ name +"&units=metric&appid=72d251b81d30ef572ae667dfe6c4ee1a")
    data = response.json()    
    cod = data['cod']
    
    i = 0
    cities = []

    # checks if response if OK
    if int(cod) == 200:
        self.completion_model.clear()

        # gets info about each element given in the api response
        for element in data["list"]:
            text = element['name'] + " - " + element["sys"]['country'] + " (" + str(element["coord"]["lat"]) + "; " + str(element["coord"]["lon"]) + ")"

            cities.append(text) # adds info to cities list

        for city in cities:
            i = i + 1
            self.completion_model.insert_with_values(  #
                position=i,                            # adds city to dropdown menu
                columns=(1,),                          #
                values=[str(city)],                    #
            )

# ---- converts the timezone of the selected city into real time ---- #
def convert_time(timezone):
    local_time = timezone//3600
    converted_datetime = local_time + int(datetime.utcnow().strftime("%H"))
    if converted_datetime > 24:
        converted_datetime = "0" + str(converted_datetime - 24)
    elif(converted_datetime<10):
        converted_datetime = "0" + str(converted_datetime)
    local_full_time = str(converted_datetime) + ":" + datetime.now().strftime("%M")
    return local_full_time


# ----- class to manage all the custom styling of the app ----- #
class style:
    def apply_enhanced_text(switch, state):
        time = int(convert_time(meteo["timezone"])[:2])
        if state:
            if time >= 19 or time < 6:
                app.set_css_classes(['light'])
                main_window.saved_loc_box.set_css_classes(['light'])
            else:
                app.set_css_classes(['dark'])
                main_window.saved_loc_box.set_css_classes(['dark'])
        else:
            if time >= 19 or time < 6:
                app.remove_css_class('light')
                main_window.saved_loc_box.remove_css_class('light')
            else:
                app.remove_css_class('dark')
                main_window.saved_loc_box.remove_css_class('dark')

    def apply_glassy(switch, state):
        global situa_box, conditions_box, daily_forecast_box
        use_glassy = settings.get_boolean('use-glassy')
        if state:
            situa_box.set_css_classes(['glassy'])
            conditions_box.set_css_classes(['glassy'])
            daily_forecast_box.set_css_classes(['glassy'])
        else:
            situa_box.remove_css_class('glassy')
            conditions_box.remove_css_class('glassy')
            daily_forecast_box.remove_css_class('glassy')

    # ---- applies gradient background ---- #
    def apply_bg(switch, active):
        if active is True:
            main_window.set_css_classes([css_classes[0], "main_window"])

    # ---- sets icon for forecast ---- #
    def get_icon(forecast, icon_size, icon):

            img = Gtk.Image()
            img.set_pixel_size(icon_size)

            try:
                icon_id = forecast["weather"][0]['icon']
            except:
                icon_id = forecast["weather"]['icon']

            if icon != None:
                img.set_from_file(icon_loc + icon)

            else:
                if icon_id == "01d":
                    img.set_from_file(icon_loc + 'weather-clear-large.svg')
                elif icon_id == "02d" or icon_id == "03d":
                    img.set_from_file(icon_loc + 'weather-few-clouds-large.svg')
                elif icon_id == "04d":
                    img.set_from_file(icon_loc + 'weather-overcast-large.svg')
                elif icon_id == "09d":
                    img.set_from_file(icon_loc + 'weather-showers-scattered-large.svg')
                elif icon_id == "10d":
                    img.set_from_file(icon_loc + 'weather-showers-large.svg')
                elif icon_id == "11d":
                    img.set_from_file(icon_loc + 'weather-storm-large.svg')
                elif icon_id == "13d":
                    img.set_from_file(icon_loc + 'weather-snow-large.svg')
                elif icon_id == "50d":
                    img.set_from_file(icon_loc + 'weather-fog-large.svg')

                # -------- night icon_ids --------- #
                elif icon_id == "01n":
                    img.set_from_file(icon_loc + 'weather-clear-night-large.svg')
                elif icon_id == "02n" or icon_id == "03n":
                    img.set_from_file(icon_loc + 'weather-few-clouds-night-large.svg')
                elif icon_id == "04n":
                    img.set_from_file(icon_loc + 'weather-overcast-large.svg')
                elif icon_id == "09n":
                    img.set_from_file(icon_loc + 'weather-showers-scattered-large.svg')
                elif icon_id == "10n":
                    img.set_from_file(icon_loc + 'weather-showers-large.svg')
                elif icon_id == "11n":
                    img.set_from_file(icon_loc + 'weather-storm-large.svg')
                elif icon_id == "13n":
                    img.set_from_file(icon_loc + 'weather-snow-large.svg')
                elif icon_id == "50n":
                    img.set_from_file(icon_loc + 'weather-fog-large.svg')

            return img

    # ---- sets icon for current weather ---- #
    def forecast_icon(icon, size, frcst):
            global css_classes, situa_img
            situa_img.set_pixel_size(size)
            
            if icon == "01d":
                situa_img.set_from_file(icon_loc + 'weather-clear-large.svg')
                css_classes = ["clear_sky", 'day']
            elif icon == "02d" or icon == "03d":
                situa_img.set_from_file(icon_loc + 'weather-few-clouds-large.svg')
                css_classes = ['few_clouds', 'day']
            elif icon == "04d":
                situa_img.set_from_file(icon_loc + 'weather-overcast-large.svg')
                css_classes = ['overcast', 'day']
            elif icon == "09d":
                situa_img.set_from_file(icon_loc + 'weather-showers-scattered-large.svg')
                css_classes = ['showers_scattered', 'day']
            elif icon == "10d":
                situa_img.set_from_file(icon_loc + 'weather-showers-large.svg')
                css_classes = ['showers_large', 'day']
            elif icon == "11d":
                situa_img.set_from_file(icon_loc + 'weather-storm-large.svg')
                css_classes = ['storm', 'day']
            elif icon == "13d":
                situa_img.set_from_file(icon_loc + 'weather-snow-large.svg')
                css_classes = ['snow', 'day']
            elif icon == "50d":
                situa_img.set_from_file(icon_loc + 'weather-fog-large.svg')
                css_classes = ['fog', 'day']

            # -------- night icons --------- # 
            elif icon == "01n":
                situa_img.set_from_file(icon_loc + 'weather-clear-night-large.svg')
                css_classes = ['clear_sky_night', 'night']
            elif icon == "02n" or icon == "03n":
                situa_img.set_from_file(icon_loc + 'weather-few-clouds-night-large.svg')
                css_classes = ['few_clouds_night', 'night']
            elif icon == "04n":
                situa_img.set_from_file(icon_loc + 'weather-overcast-large.svg')
                css_classes = ['overcast_night', 'night']
            elif icon == "09n":
                situa_img.set_from_file(icon_loc + 'weather-showers-scattered-large.svg')
                css_classes = ['showers_scattered_night', 'night']
            elif icon == "10n":
                situa_img.set_from_file(icon_loc + 'weather-showers-large.svg')
                css_classes = ['showers_large_night', 'night']
            elif icon == "11n":
                situa_img.set_from_file(icon_loc + 'weather-storm-large.svg')
                css_classes = ['storm_night', 'night']
            elif icon == "13n":
                situa_img.set_from_file(icon_loc + 'weather-snow-large.svg')
                css_classes = ['snow_night', 'night']
            elif icon == "50n":
                situa_img.set_from_file(icon_loc + 'weather-fog-large.svg')
                css_classes = ['fog_night', 'night']


    # ---- function to translate id to weather description ---- #
    def get_wttr_description(code):
        switcher = {
            230 and 200: (_('Thunderstorm with Light Rain')),
            231 and 201: (_('Thunderstorm with Rain')),
            232 and 202: (_('Thunderstorm with Heavy Rain')),
            210: (_('Light Thunderstorm')),
            211: (_('Thunderstorm')),
            212: (_('Heavy Thunderstorm')),
            221: (_('Ragged Thunderstorm')),
            300: (_('Light Drizzle')),
            301: (_('Drizzle')),
            302: (_('Heavy Drizzle')),
            310: (_('Light Drizzle Rain')),
            311: (_('Drizzle Rain')),
            312: (_('Heavy Drizzle Rain')),
            313: (_('Shower Rain and Drizzle')),
            314: (_('Heavy Rain and Drizzle')),
            321: (_('Shower Drizzle')),
            500: (_('Light Rain')),
            501: (_('Moderate Rain')),
            502: (_('Heavy Rain')),
            503: (_('Very Heavy Rain')),
            504: (_('Extreme Rain')),
            511: (_('Freezing Rain')),
            520: (_('Light Shower Rain')),
            521: (_('Shower Rain')),
            522: (_('Heavy Shower Rain')),
            531: (_('Ragged Shower Rain')),
            600: (_('Light Snow')),
            601: (_('Snow')),
            602: (_('Heavy Snow')),
            611: (_('Sleet')),
            612: (_('Light Shower Sleet')),
            613: (_('Shower Sleet')),
            615: (_('Light Rain and Snow')),
            616: (_('Rain and Snow')),
            620: (_('Light Shower Snow')),
            621: (_('Shower Snow')),
            622: (_('Heavy Shower Snow')),
            701: (_('Mist')),
            711: (_('Smoke')),
            721: (_('Haze')),
            731: (_('Sand/Dust Whirls')),
            741: (_('Fog')),
            751: (_('Sand')),
            761: (_('Dust')),
            762: (_('Volcanic Ash')),
            771: (_('Squalls')),
            781: (_('Tornado')),
            800: (_('Clear Sky')),
            801: (_('Few Clouds')),
            802: (_('Scattered Clouds')),
            803: (_('Broken Clouds')),
            804: (_('Overcast Clouds'))
        }
        return switcher.get(int(code), ('Not available'))