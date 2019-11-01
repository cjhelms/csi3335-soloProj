# author: chris helms
# class: csi 3335
# instructor: dr. david lin
# assignment: individual programming assignment
# due date: 11/1/2019

import cmd
import mysql.connector
import datetime

# OVERVIEW OF PROGRAM:
# Utilizes the cmd module of python to create a CLI
# syntax used do_[NAME] to create a command line action
# do_ functions created:
#   do_input_files - used to populate the database
#   do_route_check - used to check for routes to/from 2 cities
#   do_driver_info - used to pull info on a driver
#   do_city_check - used to check all departures/arrivals to/from a city
#   do_quit - quits program
# helper functions created:
#   precheck - performs all prechecks on tuples before insertion
#   postcheck - performs all postchecks on tables after all insertions
#   translate - translates start depart day + a travel time into the arrive day
#   travelDays - determines all days of week a route travels on (uses translate)
# all do_ functions are clearly documented in the help functionality


# IF A FUNCTION DOES NOT DO WHAT YOU EXPECT
# PLEASE READ MY HELP PROMPT
# Some inputs must be entered in a specific manner


class Program(cmd.Cmd):
    # intro displayed upon executing program
    intro = ("Bus Network. Type help or ? for list of commands. ALL Commands should "
             "be followed by a space then the arguments for the command seperated "
             "WITHOUT SPACES and ONLY COMMAS (e.g. 'input_files a,b,c,d)'.\n"
             "No input should include any quotation marks.")

    weekday = ["M", "T", "W", "R", "F"]
    weekend = ["S", "U"]
    week = ["U","M","T","W","R","F","S"]

    # try to connect to database
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="HW3335",
            password="PW3335",
            database="relationship"
        )
        cur = db.cursor()
    except Exception as e:
        print("ERROR: Failed to connect to database. Be sure the "
              "database has been imported from the mysqldump."
              "Closing program...")
        print(e)
        exit()

    # populates database with contents of input files
    def do_input_files(self, line):
        # help text
        ("This function imports the contents of 4 input files into the database.\n"
         "Enter the name of the 4 input text files without extensions.\n"
         "Seperate the names by a single comma.\n"
         "The files must be simple text files.\n"
         "The files must be in the working directory.\n"
         "The files must be comma delimited.\n"
         "The files will populate the database in the following order:\n"
         "1. routes - route_id, departure_city, destination_city, departure_state,\n"
         "        destination_state, travel_time, weekday_only, fare\n"
         "2. time_table - route_id, departure_time, run_in_weekdays, run_in_weekends\n"
         "3. bus_driver - driver_id, last_name, first_name, hometown_city,\n"
         "        hometown_state\n"
         "4. driver_assignments - driver_id, route_id, departure_time, day_of_week\n")

        # sql insert statements
        sqlInsert = ("INSERT INTO routes (route_id,departure_city,"
                     "destination_city,departure_state,destination_state,"
                     "travel_time,weekday_only,fare) VALUES (%s,%s,%s,"
                     "%s,%s,%s,%s,%s)",
                     "INSERT INTO time_table (route_id,departure_time,"
                     "run_in_weekdays,run_in_weekends) VALUES (%s,%s,%s,%s)",
                     "INSERT INTO bus_driver(driver_id,last_name,first_name,"
                     "hometown_city,hometown_state) VALUES (%s,%s,%s,%s,%s)",
                     "INSERT INTO driver_assignment(driver_id,route_id,"
                     "departure_time,day_of_week) VALUES (%s,%s,%s,%s)")

        # try to open files
        try:
            fileNames = line.split(',')
            if len(fileNames) != 4:
                raise Exception
        except:
            print('ERROR: File names were not input correctly.')
            return

        # try to import opened files
        try:
            for ndx, fn in enumerate(fileNames):
                f = open(fn.strip() + ".txt", "r")
                total = insert = 0
                # read files line by line
                for a in f:
                    total += 1
                    # create tuple from line
                    a = a.replace(" ", "")
                    a = a.strip().split(",")
                    # precheck the tuple before insertion
                    if self.precheck(a, ndx):
                        # try to prepare tuple to commit into database
                        try:
                            self.cur.execute(sqlInsert[ndx], a)
                            insert += 1
                        except Exception as e:
                            # tuple failed to insert for whatever reason
                            print("WARNING: Skipping tuple... ", a)
                            print(e)
                # postcheck the populated table
                self.postcheck(ndx)
                # tell the user what was successfully inserted
                print("DEBUG:", insert, "/", total, fn,
                      "records prepared to commit to database.")
        except Exception as e:
            # file failed to import for whatever reason
            print("ERROR:", fn, "file failed to import.")
            print(e)
            return

        # try to commit records to database
        try:
            self.db.commit()
            print("DEBUG: All prepared records committed to database.")
        except Exception as e:
            # failed to commit to actual database for whatever reason
            print("ERROR: Failed to commit records to database.")
            print(e)
            return

    # checks routes between a departure & destination city
    def do_route_check(self, line):
        # help text
        ("This function checks for routes between two cities.\n"
         "Candidate routes must have at most 2 transfers with 15-75 minute layovers.\n"
         "Enter the departure city & then the destination city with state.\n"
         "Example input: Waco,TX,Topeka,KS\n"
         "Seperate the cities by a single comma.\n"
         "The cities should not include cities (e.g. San Francisco = SanFrancisco)")

        # query used for function
        sqlQuery = ("SELECT route_id,departure_time,travel_time,"
                    "destination_city,destination_state,day_of_week "
                    "FROM time_table NATURAL JOIN routes NATURAL JOIN "
                    "driver_assignment "
                    "WHERE departure_city=%s AND departure_state=%s")
        args = line.strip().replace(" ", "").split(",") # user arguments of function
        minWait = datetime.timedelta(seconds=900) # 15 minute layover
        maxWait = datetime.timedelta(seconds=2700) # 45 minute layover
        departCity = (args[0].lower(), args[1].lower()) # departure city, state
        arriveCity = (args[2].lower(), args[3].lower()) # destnation city, state
        departure = [] # used to list assignments from departCity or candidate city
        candidate = [] # used to list of candidate transfer cities
        direct = [] # used to track solutions that are a direct route
        transfer = [] # used to track solutions that are a transfer route

        # a note on departure & candidate lists:
        # first it gathers the data:
        #   the algorithm finds ALL assignments leaving the departure city
        #   it then finds ALL assignments leaving ALL of the cities just mentioned
        # after gathering the data, it processes:
        #   for each assignment in departure list..
        #       check if it is a direct route
        #       if not direct, check if it can transfer
        #           check assignment against ALL assignments of each candidate
        #           compare layover time if arrives same day as transfer departs
        # finally, it outputs the results

        # a final note, candidate is a list of lists:
        #   it is a paired list to list of assignments leaving departure city, state
        #   nested inside is a list of all transfer candidates for each assignment

        # gather data
        try:
            # gather list of assignments LEAVING departure city, state
            self.cur.execute(sqlQuery, departCity)
            departure = self.cur.fetchall()
            if len(departure) == 0:
                raise Exception("Departure city not found in database.")
            for d in departure:
                # gather list of candidate city, state pairs
                tranCity = (d[3], d[4])
                self.cur.execute(sqlQuery, tranCity)
                candidate.append(self.cur.fetchall())
        except Exception as e:
            print("ERROR: Something went wrong while gathering data.")
            print(e)
            return

        # process data
        try:
            # go through each assignment that leaves departure city, state
            for ndx, d in enumerate(departure):
                # get destination city for given assignment
                dest = (d[3].lower(), d[4].lower())
                # check if destination city is the final destination (direct)
                if dest == arriveCity:
                    direct.append((d[0], d[1], d[2], d[5]))
                # check if can transfer to final destination (transfer)
                else:
                    # get travel time of given assignment
                    travelTime = d[1]+d[2]
                    # check each transfer city candidate for given assignment
                    for c in candidate[ndx]:
                        # get destination city of transfer candidate assignment
                        dest = (c[3].lower(), c[4].lower())
                        # check if they arrive/leave on the same day
                        if dest == arriveCity:
                            # check if layover time is acceptable
                            arriveDay = self.translate(d[5],travelTime)
                            ndxT = self.week.index(c[5])
                            ndxD = self.week.index(arriveDay)
                            flag = False
                            arriveTime = travelTime - datetime.timedelta(days=travelTime.days)
                            time = c[1] - arriveTime
                            # if arrive same day, compare layover
                            if c[5] == arriveDay:
                                if time >= minWait and time <= maxWait:
                                    flag = True
                            # if layover spans a day
                            elif c[1] < maxWait:
                                if ndxT - ndxD == 1 or ndxT - ndxD == -6:
                                    flag = True
                                    time += datetime.timedelta(days=1)     
                            # if layover spans a day, other direction                               
                            elif (datetime.timedelta(days=1)-c[1]) < maxWait:
                                if ndxD - ndxT == 1 or ndxD - ndxD == -6:
                                    flag = True
                            # if layover is ok, add to transfer solution
                            if flag:
                                transfer.append((d[0], d[1], d[2], d[3], d[4],
                                                    time, c[0], c[1], c[2], c[5]))
        except Exception as e:
            print("ERROR: Something went wrong while processing data.")
            print(e)
            return

        # output data
        try:
            if len(direct) == 0 and len(transfer) == 0:
                print("No routes were found.")
            else:
                if len(direct) > 0:
                    print("Direct routes:")
                    print("(route id, departure time, travel time, day of week "
                    "of departure)")
                    for d in direct:
                        print(d[0], d[1], d[2], d[3])
                else:
                    print("No direct routes.")
                if len(transfer) > 0:
                    print("Transfer routes:")
                    print("(route id, departure time, travel time, transfer city, "
                    "transfer state, layover time, transfer departure time, transfer "
                    "travel time, day of week of departure")
                    for t in transfer:
                        print(t[0], t[1], t[2], t[3], t[4], t[5], t[6],
                              t[7], t[8], t[9])
                else:
                    print("No transfer routes.")
        except Exception as e:
            print("ERROR: Something went wrong while outputting data.")
            print(e)
            return

    # returns driver information for requested driver
    def do_driver_info(self, line):
        # help text
        ("This function returns the driver information for the given name or ID.\n"
         "Driver information includes all bus driver attributes & assignments.\n"
         "To search by name, enter 'name' followed by the first & last name.\n"
         "To search by ID, enter 'id' followed by the driver id.\n"
         "Search parameters are CASE SENSITIVE.\n"
         "Enter input in format:\n"
         "    name,[first],[last]\n"
         "    id,[ID]\n"
         "The first & last name must have no spaces (e.g. Mary Ann = MaryAnn).\n"
         "If there are many drivers with the same name, all will be returned.")

        driver = None # stores driver tuple from mysql
        # sql queries
        sqlName = ("SELECT * "
                   "FROM bus_driver "
                   "WHERE first_name=%s AND last_name=%s")
        sqlId = ("SELECT * "
                 "FROM bus_driver "
                 "WHERE driver_id=%s")
        sqlAssign = ("SELECT * "
                     "FROM driver_assignment "
                     "WHERE driver_id=%s")
        args = line.strip().split(',') # stores arguments from command

        # check if user input is valid
        if args[0] != "name" and args[0] != "id" and args[0]:
            print("ERROR: Unknown search parameter.")
            return

        # gather data
        # search by name
        try:
            if args[0] == "name":
                if len(args) > 3:
                    raise Exception("Search by name requires first, last name")
                self.cur.execute(sqlName, (args[1], args[2]))
                driver = self.cur.fetchall()
        except Exception as e:
            print("ERROR: Something went wrong gathering data with name search.")
            print(e)

        # search by id
        try:
            if args[0] == "id":
                if len(args) > 2:
                    raise Exception("Search by id requires one id")
                self.cur.execute(sqlId, (args[1],))
                driver = self.cur.fetchall()
        except Exception as e:
            print("ERROR: Something went wrong gathering data with id search.")
            print(e)

        # process data
        # get driver assignments
        try:
            assign = []
            # if multiple drivers, get assignments for both
            for d in driver:
                self.cur.execute(sqlAssign, (d[0],))
                assign.append(self.cur.fetchall())
        except Exception as e:
            print("ERROR: Something went wrong while gathering assignment data.")
            print(e)

        # output data
        try:
            if len(driver) > 0:
                for ndx, d in enumerate(driver):
                    print("Driver Info:")
                    print(d[0], d[1], d[2], d[3], d[4])
                    if len(assign[ndx]) > 0:
                        print("Assignments:")
                        for a in assign[ndx]:
                            print(a[1], a[2], a[3])
                    else:
                        print("Driver has no assignments.")
            else:
                print("No driver found.")
        except Exception as e:
            print("ERROR: Something went wrong while outputting data.")
            print(e)

    # returns all arrivals & departures for bus routes at a city on a day
    def do_city_check(self, line):
        # help text
        ("Returns all arrivals & departures for bus routes at a city on a day.\n"
         "Enter the city name, state, & day of the week seperated by a comma.\n"
         "City names should contain no spaces (e.g. San Francisco = SanFrancisco).\n"
         "Allowed day entries are: M, T, W, R, F, S, U\n"
         "Routes are sorted in order of time.")

        day = datetime.timedelta(seconds=86400) # seconds in a day
        # mysql queries
        sqlDepart = ("SELECT route_id,departure_time "
                     "FROM routes NATURAL JOIN time_table "
                     "NATURAL JOIN driver_assignment "
                     "WHERE departure_city=%s AND departure_state=%s "
                     "AND day_of_week=%s")
        sqlArrive = ("SELECT route_id,departure_time,travel_time "
                     "FROM routes NATURAL JOIN time_table "
                     "NATURAL JOIN driver_assignment "
                     "WHERE destination_city=%s AND destination_state = %s AND "
                     "day_of_week=%s")
        line = line.replace(" ", "") # process user input
        args = line.strip().split(',') # store user input in args
        if len(args) != 3:
            print("ERROR: 3 arguments required for city_check.")
            return

        # gather data
        # get all arrivals & departures to/from city
        try:
            if args[2] not in self.weekend and args[2] not in self.weekday:
                raise Exception("ERROR: Day not valid.")
            self.cur.execute(sqlDepart, args)
            depart = self.cur.fetchall()
            self.cur.execute(sqlArrive, args)
            temp = self.cur.fetchall()
        except Exception as e:
            print("ERROR: Something went wrong while gathering data.")
            print(e)
            return

        # process data
        # figure out when arrivals arrive & sort by departure/arrival time
        try:
            arrive = []
            depart.sort(key=lambda r: r[1])
            for a in temp:
                if a[1]+a[2] < day:
                    arrive.append((a[0], a[1]+a[2]))
            arrive.sort(key=lambda r: r[1])
        except Exception as e:
            print("ERROR: Something went wrong while processing data.")
            print(e)
            return

        # output data
        try:
            if len(depart) == 0 & len(arrive) == 0:
                print("City not found or no departures/arrivals for given day.")
            else:
                print("Departures:")
                if len(depart) > 0:
                    for d in depart:
                        print(d[0], d[1])
                else:
                    print("No departures for given day.")
                print("Arrivals:")
                if len(arrive) > 0:
                    for a in arrive:
                        print(a[0], a[1])
                else:
                    print("No arrivals for given day.")
        except Exception as e:
            print("ERROR: Something went wrong while outputting data.")
            print(e)

    # quits program
    def do_quit(self, line):
        # help text
        "Quits the program."

        # self.cur.execute("DELETE FROM driver_assignment")
        # self.cur.execute("DELETE FROM bus_driver")
        # self.cur.execute("DELETE FROM time_table")
        # self.cur.execute("DELETE FROM routes")
        # self.db.commit()

        return True

    # prechecks tuples before inserting
    # ndx = 0: routes
    # ndx = 1: time_table
    # ndx = 2: bus_driver
    # ndx = 3: driver_assignments
    def precheck(self, tup, ndx):
        flag = True # used to determine if a check has failed
        if ndx == 1:
            # check (run_in_weekdays/ends) against routes(weekday_only)
            sqlQuery = ("SELECT weekday_only "
                        "FROM routes "
                        "WHERE route_id=%s")
            try:
                # get weekday_only from routes table
                self.cur.execute(sqlQuery, (tup[0],))
                check = self.cur.fetchall()
                if len(check) > 0:
                    check = check[0][0]
                    # route is weekday only, tuple runs weekend or not weekday
                    if check and (tup[2] == "0" or tup[3] == "1"):
                        flag = False
                if not flag:
                    print("WARNING: Skipping tuple... ", tup)
                    print("Tuple failed time_table precheck.")
                    print("Discrepency in weekday/weekend route times.")
            except Exception as e:
                print("ERROR: Something went wrong prechecking time_table tuple.")
                print(e)
                exit()
        if ndx == 3:
            # check (day_of_week) against time_table(run_in_weekdays/ends)
            sqlQuery = ("SELECT run_in_weekdays,run_in_weekends "
                        "FROM time_table "
                        "WHERE route_id=%s")
            try:
                # get run_in_weekdays/ends from time_table table
                self.cur.execute(sqlQuery, (tup[1],))
                check = self.cur.fetchall()
                if len(check) > 0:
                    runsWeekday = check[0][0]
                    runsWeekend = check[0][1]
                    # check if assignment consistent with time table
                    if runsWeekday and not runsWeekend and tup[3] in self.weekend:
                        flag = False
                    elif runsWeekend and not runsWeekday and tup[3] in self.weekday:
                        flag = False
                if not flag:
                    print("WARNING: Tuple failed driver_assignment precheck... ",
                          tup)
                    print("Route does not run on day of week.")
            except Exception as e:
                print("ERROR: Something went wrong prechecking driver_assignment "
                      "tuple.")
                print(e)
                exit()
            # check driver's assignment will not overlap existing
            # check driver has enough rest
            # check if a route exists to get driver to next location
            #   note that the last check ONLY checks if there is a route at all
            #   since it is unknown when the route may leave, it is only checked if
            #       there will be enough rest without the transfer
            try:
                eTravelTime = 0 # existing travel time
                eDaysTraveling = [] # days existing route travels
                eDepartTime = 0 # existing departure time
                eArriveTime = 0 # existing arrival time
                nTravelTime = 0 # new tuple travel time
                nDaysTraveling = [] # days new tuple travels
                nDepartTime = 0 # new tuple departure time
                nArriveTime = 0 # new tuple arrival time
                eRest = 0 # required rest for existing route
                nRest = 0 # required rest for new tuple
                nDepartCity = "" # new tuple departure city
                nDepartState = "" # new tuple departure state
                nArriveCity = "" # new tuple arrival city
                nArriveState = "" # new tuple arrival state
                eDepartCity = "" # existing departure city
                eDepartState = "" # existing departure state
                eArriveCity = "" # existing arrival city
                eArriveState = "" # existing arrival state
                bufferTime = 1000 # buffer time between arriving/departing
                message = "" # message to display if flag is set to false

                # gather assignment data for driver in tuple
                try:                
                    self.cur.execute("SELECT route_id,departure_time,day_of_week "
                    "FROM driver_assignment "
                    "WHERE driver_id=%s",(tup[0],))
                    assgns = self.cur.fetchall()
                except Exception as e:
                    print("ERROR: Failed to load existing tuple route...")
                    print(e)

                # assign new tuple data to easy to read variables
                try:
                    self.cur.execute("SELECT travel_time,departure_city,"
                    "departure_state,destination_city,destination_state "
                    "FROM routes "
                    "WHERE route_id=%s",(tup[1],))
                    temp = self.cur.fetchall()[0]
                    nTravelTime = temp[0]
                    nDepartCity = temp[1]
                    nDepartState = temp[2]
                    nArriveCity = temp[3]
                    nArriveState = temp[4]
                except Exception as e:
                    print("ERROR: Failed to load new tuple route in check...")
                    print(e)
                    return
                
                # continue assigning new tuple to easy to read variables
                temp = datetime.datetime.strptime(tup[2], "%H:%M")
                nDepartTime = datetime.timedelta(hours=temp.hour, minutes=temp.minute)
                nDaysTraveling.append(tup[3])
                temp = self.translate(nDaysTraveling[0], nTravelTime + nDepartTime)
                nArriveTime = nDepartTime + nTravelTime
                nArriveTime -= datetime.timedelta(days=nArriveTime.days)
                nRest = nTravelTime/2

                if temp != nDaysTraveling[0]:
                    res = self.travelDays(nDaysTraveling[0],nTravelTime + nDepartTime)
                    for r in res:
                        nDaysTraveling.append(r)
                    
                # print("NEW: ", nDepartTime, nArriveTime, nDaysTraveling)

                # check new tuple against each assignment for driver
                for a in assgns:
                    # assign existing to easy to read variables
                    try:
                        self.cur.execute("SELECT travel_time,departure_city,"
                        "departure_state,destination_city,destination_state "
                        "FROM routes "
                        "WHERE route_id=%s",(a[0],))
                        temp = self.cur.fetchall()[0]
                        eTravelTime = temp[0]
                        eDepartCity = temp[1]
                        eDepartState = temp[2]
                        eArriveCity = temp[3]
                        eArriveState = temp[4]
                    except Exception as e:
                        print("ERROR: Failed to load existing tuple in check...")
                        print(e)

                    eRest = eTravelTime/2
                    eDaysTraveling.append(a[2])
                    eDepartTime = a[1]
                    temp = self.translate(eDaysTraveling[0], eTravelTime + eDepartTime)
                    eArriveTime = eDepartTime + eTravelTime
                    eArriveTime -= datetime.timedelta(days=eArriveTime.days)
                    
                    if temp != eDaysTraveling[0]:
                        res = self.travelDays(eDaysTraveling[0],eTravelTime + eDepartTime)
                        for r in res:
                            eDaysTraveling.append(r)

                    # print("OLD: ", eDepartTime, eArriveTime, eDaysTraveling)

                    # check start day of new tuple
                    if nDaysTraveling[0] in eDaysTraveling:
                        # if new leaves same as existing
                        if nDaysTraveling[0] == eDaysTraveling[0]:
                            # if new arrives same as existing leaves
                            if nDaysTraveling[-1] == eDaysTraveling[0]:
                                # if new leaves before existing
                                if nDepartTime < eDepartTime:
                                    # if existing leaves before new arrives
                                    if eDepartTime < nArriveTime: 
                                        flag = False
                                        message = "Assignment leaves while existing travels."
                                    # check rest time
                                    elif eDepartTime < nArriveTime + nRest:
                                        flag = False
                                        message = "Assignment does not allow enough rest."
                                # if existing leaves before new
                                elif eDepartTime < nDepartTime:
                                    # if new leaves before existing arrives
                                    if nDepartTime < eArriveTime:
                                        flag = False
                                        message = "Assignment leaves before existing arrives."
                                    # check rest time
                                    elif nDepartTime < eArriveTime + eRest:
                                        flag = False
                                        message = "Assignment does not allow enough rest."
                            # otherwise, check if new leaving day existing arrives
                            elif nDaysTraveling[0] == eDaysTraveling[-1]:
                                if nDepartTime < eArriveTime:
                                    flag = False
                                    message = "Assignment leaves while existing travels."
                        else:
                            flag = False
                            message = "Assignment leaves while existing travels."
                    # if rest & overlap are ok, check if driver can get to new city
                    # check new leaving second
                    if flag and nDaysTraveling[0] == self.translate(eDaysTraveling[-1],eArriveTime + eRest):
                        bufferTime = (eArriveTime + eRest) - datetime.timedelta(days=(eArriveTime + eRest).days)
                        # check rest over multiple days
                        if nDepartTime < bufferTime:
                            flag = False
                            message = "Assignment does not allow enough rest."
                        # if driver is not in departure city for new assg
                        elif eArriveCity.lower() != nDepartCity.lower():
                            # check if route exists to get him there with 1 hour buffer
                            try:
                                self.cur.execute("SELECT COUNT(*) "
                                "FROM routes "
                                "WHERE departure_city=%s,departure_state=%s,"
                                "destination_city=%s,destination_state=%s",(eArriveCity,eArriveState,nDepartCity,nDepartState))
                                temp = self.cur.fetchall()[0][0]
                                # if not, flag = false
                                if temp == 0:
                                    flag = False
                                    message = "Existing assignment leaves driver in city with no way to reach new assignment."
                            except Exception as e:
                                print("ERROR: Something went wrong checking for existing route in check.")
                                print(e)
                                return
                    # check end day of new tuple
                    if flag and eDaysTraveling[0] == self.translate(nDaysTraveling[-1],nArriveTime + nRest):
                        bufferTime = (nArriveTime + nRest) - datetime.timedelta(days=(nArriveTime + nRest).days)
                        if eDepartTime < bufferTime:
                            flag = False
                            message = "Assignment does not allow enough rest."
                        # if driver is not in departure city for existing assg
                        elif nArriveCity.lower() != eDepartCity.lower():
                            # check if route exists to get him there with 1 hour buffer
                            try:
                                self.cur.execute("SELECT COUNT(*) "
                                "FROM routes "
                                "WHERE departure_city=%s,departure_state=%s,"
                                "destination_city=%s,destination_state=%s",(nArriveCity,nArriveState,eDepartCity,eDepartState))
                                temp = self.cur.fetchall()[0][0]
                                # if not, flag = false
                                if temp == 0:
                                    flag = False
                                    message = "New assignment leaves driver in city with no way to reach existing assignment."
                            except Exception as e:
                                print("ERROR: Something went wrong checking for existing route in check.")
                                print(e)
                                return
                    # print warning message if flag if check failed
                    if flag == False:
                        print("WARNING: Skipping tuple... ", tup)
                        print(message)
            except Exception as e:
                print("ERROR: Something went wrong while checking for assignment overlap.")
                print(e)
                return
        # bad user input
        elif ndx < 0 or ndx > 3:
            print("ERROR: Check function requires index between 0 & 3.")
            flag = False
        return flag

    # postchecks table after tuples have been entered
    # ndx = 0: routes
    # ndx = 1: time_table
    # ndx = 2: bus_driver
    # ndx = 3: driver_assignments
    def postcheck(self, ndx):
        self.cur.execute("SELECT route_id,weekday_only FROM routes")
        routes = self.cur.fetchall()
        if ndx == 1:
            # check (run_in_weekdays/ends) against routes(weekday_only)
            for r in routes:
                runsWeekend = False
                if r[1] == 0:
                    self.cur.execute("SELECT run_in_weekdays,run_in_weekends "
                    "FROM time_table "
                    "WHERE route_id=%s",(r[0],))
                    timetable = self.cur.fetchall()
                    # check all time table
                    for t in timetable:
                        if t[1]:
                            runsWeekend = True
                    # if route doesn't run on weekend & it should
                    if not runsWeekend and not routes[1]:
                        print("WARNING: Route only runs on weekdays...",r[0])
        if ndx == 3:
            # check all routes have driver on all days of week &/or weekend
            for r in routes:    
                self.cur.execute("SELECT day_of_week "
                "FROM driver_assignment "
                "WHERE route_id=%s",(r[0],))
                assign = self.cur.fetchall()
                daysRunning = []
                for a in assign:
                    daysRunning.append(a[0])
                # for each day of the week
                for day in self.weekday:
                    # if day is not days it runs
                    if day not in daysRunning:
                        print("WARNING: Route not running on day...", r[0], day)
                # if weekday only
                if r[1] == 0:
                    # for each day of weekend
                    for day in self.weekend:
                        # if day is not days it runs
                        if day not in daysRunning:
                            print("WARNING: Route not running on day...", r[0], day)
        # bad user input
        elif ndx < 0 or ndx > 3:
            print("ERROR: Check function requires index between 0 & 3.")
        return 0

    def translate(self, day, time):
        ndx = self.week.index(day)
        travelDays = time.days
        arriveNdx = (ndx + travelDays) % len(self.week)
        # print("OLD DAY: ", day)
        # print("TRAVEL DAYS: ", travelDays)
        # print("NEW DAY: ", self.week[arriveNdx])
        return self.week[arriveNdx]

    def travelDays(self, startDay, travelTime):
        ndx = self.week.index(startDay)
        ndxEnd = self.week.index(self.translate(startDay, travelTime))
        res = []
        
        while ndx != ndxEnd:
            ndx = (ndx+1)%len(self.week)
            res.append(self.week[ndx])

        return res

Program().cmdloop()
