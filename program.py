import cmd
import mysql.connector
import datetime


class Program(cmd.Cmd):
    # intro displayed upon executing program
    intro = ("Bus Network. Type help or ? for list of commands. Commands should "
             "be followed by a space then the arguments for the command "
             "(e.g. 'input_files a,b,c,d)'.")

    weekday = ["M", "T", "W", "R", "F"]
    weekend = ["S", "U"]

    # try to connect to database
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="password123",
            database="relationship"
        )
        cur = db.cursor()
    except Exception as e:
        print("ERROR: Failed to connect to database. Be sure the "
              "database has been imported from the mysqldump."
              "Closing program...")
        print(e)
        quit()

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
                    if self.precheck(a, ndx):
                        # try to prepare tuple to commit into database
                        try:
                            self.cur.execute(sqlInsert[ndx], a)
                            insert += 1
                        except Exception as e:
                            print("WARNING: Skipping tuple... ", a)
                            print(e)
                insert -= self.postcheck(ndx)
                print("DEBUG:", insert, "/", total, fn,
                      "records prepared to commit to database.")
        except Exception as e:
            print("ERROR:", fn, "file failed to import.")
            print(e)
            return

        # try to commit records to database
        try:
            self.db.commit()
            print("DEBUG: All records committed to database.")
        except Exception as e:
            print("ERROR: Failed to commit records to database.")
            print(e)
            return

    # checks routes between a departure & destination city
    def do_route_check(self, line):
        # help text
        ("This function checks for routes between two cities.\n"
         "Candidate routes must have at most 2 transfers with 15-75 minute layovers.\n"
         "Enter the name of the departure city & then the destination city with state.\n"
         "Example input: Waco,TX,Topeka,KS\n"
         "Seperate the cities by a single comma.\n"
         "The cities should not include cities (e.g. San Francisco = SanFrancisco)")

        sqlQuery = ("SELECT route_id,departure_time,travel_time,"
                    "destination_city,destination_state,day_of_week "
                    "FROM time_table NATURAL JOIN routes NATURAL JOIN "
                    "driver_assignment "
                    "WHERE departure_city=%s AND departure_state=%s")
        args = line.strip().replace(" ", "").split(",")
        minWait = datetime.timedelta(seconds=900)
        maxWait = datetime.timedelta(seconds=2700)
        depart = []
        candidate = []

        try:
            self.cur.execute(sqlQuery, (args[0], args[1]))
            depart = self.cur.fetchall()
            for d in depart:
                self.cur.execute(sqlQuery, (d[3], d[4]))
                candidate.append(self.cur.fetchall())
        except Exception as e:
            print("ERROR: Something went wrong while gathering data.")
            print(e)

        try:
            direct = []
            transfer = []
            for ndx, d in enumerate(depart):
                if (d[3], d[4]) == (args[2], args[3]):
                    direct.append((d[0], d[1], d[2], d[5]))
                else:
                    for c in candidate[ndx]:
                        if (c[3], c[4]) == (args[2], args[3]) and d[5] == c[5]:
                            time = c[1]-(d[1]+d[2])
                            if time > minWait and time < maxWait:
                                transfer.append(d[0], d[1], d[2], d[3], d[4],
                                                time, c[0], c[1], c[2], c[5])
        except Exception as e:
            print("ERROR: Something went wrong while processing data.")
            print(e)

        try:
            if len(direct) == 0 and len(transfer) == 0:
                print("No routes were found.")
            else:
                if len(direct) > 0:
                    print("Direct routes:")
                    for d in direct:
                        print(d[0], d[1], d[2])
                else:
                    print("No direct routes.")
                if len(transfer) > 0:
                    print("Transfer routes:")
                    for t in transfer:
                        print(t[0], t[1], t[2], t[3], t[4], t[5], t[6],
                              t[7], t[8], t[9])
                else:
                    print("No transfer routes.")
        except Exception as e:
            print("ERROR: Something went wrong while outputting data.")
            print(e)

    # returns driver information for requested driver
    def do_driver_info(self, line):
        # help text
        ("This function returns the driver information for the given name or ID.\n"
         "Driver information includes all bus driver attributes & driver assignments.\n"
         "To search by name, enter 'name' followed by the first & last name.\n"
         "To search by ID, enter 'id' followed by the driver id.\n"
         "Search parameters are CASE SENSITIVE.\n"
         "Enter input in format:\n"
         "    name,[first],[last]\n"
         "    id,[ID]\n"
         "The first & last name must have no spaces (e.g. Mary Ann = MaryAnn).\n"
         "If there are many drivers with the same name, all will be returned.")

        driver = None
        sqlName = ("SELECT * "
                   "FROM bus_driver "
                   "WHERE first_name=%s AND last_name=%s")
        sqlId = ("SELECT * "
                 "FROM bus_driver "
                 "WHERE driver_id=%s")
        sqlAssign = ("SELECT * "
                     "FROM driver_assignment "
                     "WHERE driver_id=%s")
        args = line.strip().split(',')

        if args[0] != "name" and args[0] != "id" and args[0]:
            print("ERROR: Unknown search parameter.")
            return

        try:
            if args[0] == "name":
                if len(args) > 3:
                    raise Exception("Search by name requires first, last name")
                self.cur.execute(sqlName, (args[1], args[2]))
                driver = self.cur.fetchall()
        except Exception as e:
            print("ERROR: Something went wrong gathering data with name search.")
            print(e)

        try:
            if args[0] == "id":
                if len(args) > 2:
                    raise Exception("Search by id requires one id")
                self.cur.execute(sqlId, (args[1],))
                driver = self.cur.fetchall()
        except Exception as e:
            print("ERROR: Something went wrong gathering data with id search.")
            print(e)

        try:
            assign = []
            for d in driver:
                self.cur.execute(sqlAssign, (d[0],))
                assign.append(self.cur.fetchall())
        except Exception as e:
            print("ERROR: Something went wrong while gathering assignment data.")
            print(e)

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

        day = datetime.timedelta(seconds=86400)
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
        line = line.replace(" ", "")
        args = line.strip().split(',')
        if len(args) != 3:
            print("ERROR: 3 arguments required for city_check.")
            return

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

        try:
            arrive = []
            depart.sort(key=lambda r: r[1])
            for a in temp:
                if a[1]+a[2] < day:
                    arrive.append((a[0], a[1]))
            arrive.sort(key=lambda r: r[1])
        except Exception as e:
            print("ERROR: Something went wrong while processing data.")
            print(e)
            return

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

        return True

    # prechecks tuples before inserting
    # ndx = 0: routes
    # ndx = 1: time_table
    # ndx = 2: bus_driver
    # ndx = 3: driver_assignments
    def precheck(self, tup, ndx):
        flag = True
        if ndx == 1:
            # check (run_in_weekdays/ends) against routes(weekday_only)
            sqlQuery = ("SELECT weekday_only "
                        "FROM routes "
                        "WHERE route_id=%s")
            try:
                self.cur.execute(sqlQuery, (tup[0],))
                check = self.cur.fetchall()
                if len(check) > 0:
                    check = check[0][0]
                    if check and (tup[2] == "0" or tup[3] == "1"):
                        flag = False
                    elif not check and (tup[2] == "0" or tup[3] == "0"):
                        flag = False
                else:
                    flag = False
                if not flag:
                    print("WARNING: Tuple failed precheck... ", tup)
                    print("Discrepency in weekday/weekend route times.")
            except Exception as e:
                print("ERROR: Something went wrong prechecking time_table tuple.")
                print(e)
        elif ndx == 3:
            # check (day_of_week) against time_table(run_in_weekdays/ends)
            # check driver's assignment will not overlap existing
            # check driver will have enough rest
            pass
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
        if ndx == 3:
            # check all assignments allow time/routes to reach adjacent assignments
            # check all routes have driver on all days of week &/or weekend
            pass
        elif ndx < 0 or ndx > 3:
            print("ERROR: Check function requires index between 0 & 3.")
        return 0


Program().cmdloop()
