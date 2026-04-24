-- AvionDash Docker – Database Seed (MySQL 8.0)
-- Users are created by the Python app on startup (init_db.py)
-- to avoid bcrypt hash encoding issues in SQL.
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS airports (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  iata_code CHAR(3) NOT NULL UNIQUE, icao_code CHAR(4),
  name VARCHAR(100) NOT NULL, city VARCHAR(60) NOT NULL, country VARCHAR(60) NOT NULL,
  lat DECIMAL(9,6) NOT NULL, lon DECIMAL(9,6) NOT NULL,
  timezone VARCHAR(40), elevation_ft INT, runways TINYINT DEFAULT 2,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS aircraft (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  tail_number VARCHAR(10) NOT NULL UNIQUE, model VARCHAR(50) NOT NULL,
  manufacturer VARCHAR(50) NOT NULL, capacity SMALLINT NOT NULL, range_nm INT NOT NULL,
  status ENUM('active','maintenance','grounded','retired') DEFAULT 'active',
  engine_type VARCHAR(30), year_manufactured YEAR,
  last_maintenance DATETIME, next_maintenance DATETIME,
  flight_hours DECIMAL(10,1) DEFAULT 0.0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS flights (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  flight_number VARCHAR(10) NOT NULL, origin_iata CHAR(3) NOT NULL,
  destination_iata CHAR(3) NOT NULL, aircraft_id INT UNSIGNED,
  status ENUM('scheduled','boarding','departed','en_route','landed','cancelled','diverted','delayed') DEFAULT 'scheduled',
  departure_time DATETIME NOT NULL, arrival_time DATETIME,
  gate VARCHAR(5), altitude_ft INT, speed_kts INT,
  lat DECIMAL(9,6), lon DECIMAL(9,6), fuel_remaining_pct DECIMAL(5,2),
  delay_minutes INT DEFAULT 0, notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_status(status), INDEX idx_fn(flight_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE, email VARCHAR(120) NOT NULL UNIQUE,
  hashed_password VARCHAR(255) NOT NULL, full_name VARCHAR(100),
  role ENUM('admin','operator','viewer') DEFAULT 'viewer',
  is_active TINYINT(1) DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP, last_login DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Airports
INSERT INTO airports (iata_code,icao_code,name,city,country,lat,lon,timezone,elevation_ft,runways) VALUES
('JFK','KJFK','John F. Kennedy Intl','New York','United States',40.639751,-73.778925,'America/New_York',13,4),
('LAX','KLAX','Los Angeles Intl','Los Angeles','United States',33.942791,-118.410042,'America/Los_Angeles',125,4),
('ORD','KORD',"O'Hare Intl",'Chicago','United States',41.978603,-87.904842,'America/Chicago',672,8),
('ATL','KATL','Hartsfield-Jackson Atlanta Intl','Atlanta','United States',33.636719,-84.428067,'America/New_York',1026,5),
('DFW','KDFW','Dallas/Fort Worth Intl','Dallas','United States',32.896828,-97.037997,'America/Chicago',607,7),
('DEN','KDEN','Denver Intl','Denver','United States',39.856094,-104.673738,'America/Denver',5431,6),
('SFO','KSFO','San Francisco Intl','San Francisco','United States',37.618972,-122.374889,'America/Los_Angeles',13,4),
('SEA','KSEA','Seattle-Tacoma Intl','Seattle','United States',47.449888,-122.311777,'America/Los_Angeles',433,3),
('MIA','KMIA','Miami Intl','Miami','United States',25.795865,-80.287046,'America/New_York',8,4),
('BOS','KBOS','Boston Logan Intl','Boston','United States',42.364347,-71.005181,'America/New_York',19,4),
('LHR','EGLL','London Heathrow','London','United Kingdom',51.477500,-0.461389,'Europe/London',83,2),
('CDG','LFPG','Charles de Gaulle','Paris','France',49.012779,2.550000,'Europe/Paris',392,4),
('FRA','EDDF','Frankfurt Airport','Frankfurt','Germany',50.033333,8.570556,'Europe/Berlin',364,4),
('AMS','EHAM','Amsterdam Schiphol','Amsterdam','Netherlands',52.308056,4.764167,'Europe/Amsterdam',-11,6),
('MAD','LEMD','Madrid-Barajas','Madrid','Spain',40.472222,-3.560833,'Europe/Madrid',2000,4),
('DXB','OMDB','Dubai Intl','Dubai','UAE',25.252778,55.364444,'Asia/Dubai',62,2),
('SIN','WSSS','Singapore Changi','Singapore','Singapore',1.350189,103.994433,'Asia/Singapore',22,3),
('NRT','RJAA','Tokyo Narita','Tokyo','Japan',35.765278,140.385556,'Asia/Tokyo',141,2),
('HND','RJTT','Tokyo Haneda','Tokyo','Japan',35.549444,139.779167,'Asia/Tokyo',21,4),
('PEK','ZBAA','Beijing Capital Intl','Beijing','China',40.080111,116.584556,'Asia/Shanghai',115,3),
('HKG','VHHH','Hong Kong Intl','Hong Kong','China',22.308919,113.914603,'Asia/Hong_Kong',28,2),
('SYD','YSSY','Sydney Kingsford Smith','Sydney','Australia',-33.946111,151.177222,'Australia/Sydney',21,3),
('YYZ','CYYZ','Toronto Pearson Intl','Toronto','Canada',43.677222,-79.630556,'America/Toronto',569,5),
('GRU','SBGR','Sao Paulo Guarulhos Intl','Sao Paulo','Brazil',-23.432075,-46.469511,'America/Sao_Paulo',2459,3),
('JNB','FAOR','OR Tambo Intl','Johannesburg','South Africa',-26.133694,28.242317,'Africa/Johannesburg',5558,3);

-- Aircraft
INSERT INTO aircraft (tail_number,model,manufacturer,capacity,range_nm,status,engine_type,year_manufactured,last_maintenance,next_maintenance,flight_hours) VALUES
('N-AVD001','B737-800','Boeing',189,3060,'active','CFM56-7B',2018,'2024-11-10','2025-05-10',14230.5),
('N-AVD002','B737-MAX9','Boeing',193,3550,'active','LEAP-1B',2022,'2024-10-01','2025-04-01',5120.0),
('N-AVD003','A320neo','Airbus',165,3400,'active','LEAP-1A',2021,'2024-12-01','2025-06-01',7840.3),
('N-AVD004','A321XLR','Airbus',220,4700,'active','LEAP-1A',2023,'2025-01-15','2025-07-15',2100.8),
('N-AVD005','B787-9','Boeing',296,7635,'active','GEnx-1B',2020,'2024-09-20','2025-03-20',11520.0),
('N-AVD006','B787-10','Boeing',330,6430,'active','GEnx-1B',2021,'2024-11-01','2025-05-01',9800.2),
('N-AVD007','A350-900','Airbus',369,8100,'active','Trent XWB',2019,'2024-08-15','2025-02-15',16000.0),
('N-AVD008','A350-1000','Airbus',410,8700,'maintenance','Trent XWB',2020,'2025-01-01','2025-07-01',12500.0),
('N-AVD009','B777-300ER','Boeing',396,7370,'active','GE90-115B',2017,'2024-10-20','2025-04-20',22300.5),
('N-AVD010','A380-800','Airbus',555,8200,'active','Trent 970',2016,'2024-07-01','2025-01-01',29000.0),
('N-AVD011','E195-E2','Embraer',146,2850,'active','PW1900G',2023,'2025-02-01','2025-08-01',1800.0),
('N-AVD012','CRJ-900','Bombardier',90,1550,'active','CF34-8C5',2019,'2024-11-20','2025-05-20',8900.0),
('N-AVD013','A220-300','Airbus',130,3400,'active','PW1500G',2022,'2025-01-05','2025-07-05',4100.0),
('N-AVD014','B737-700','Boeing',140,3200,'maintenance','CFM56-7B',2014,'2025-02-15','2025-08-15',28000.0),
('N-AVD015','B757-200','Boeing',200,3900,'active','RR RB211',2013,'2024-12-20','2025-06-20',41200.0);

-- Flights
INSERT INTO flights (flight_number,origin_iata,destination_iata,aircraft_id,status,departure_time,arrival_time,gate,altitude_ft,speed_kts,lat,lon,fuel_remaining_pct,delay_minutes,notes) VALUES
('AVD001','JFK','LHR',5,'en_route', NOW()-INTERVAL 4 HOUR,NOW()+INTERVAL 3 HOUR,'B12',37000,490,46.500,-35.200,62.0,0,NULL),
('AVD002','LAX','NRT',7,'en_route', NOW()-INTERVAL 7 HOUR,NOW()+INTERVAL 5 HOUR,'A04',39000,485,50.100,-175.300,44.5,0,NULL),
('AVD003','LHR','DXB',9,'en_route', NOW()-INTERVAL 3 HOUR,NOW()+INTERVAL 4 HOUR,'T5-C',36000,480,40.100,28.500,55.0,0,NULL),
('AVD004','DXB','SIN',7,'en_route', NOW()-INTERVAL 5 HOUR,NOW()+INTERVAL 2 HOUR,'C14',38000,475,12.400,80.200,40.0,0,NULL),
('AVD005','SFO','HKG',5,'en_route', NOW()-INTERVAL 9 HOUR,NOW()+INTERVAL 5 HOUR,'G22',38000,488,42.000,160.000,30.0,0,NULL),
('AVD006','ATL','LHR',5,'en_route', NOW()-INTERVAL 6 HOUR,NOW()+INTERVAL 3 HOUR,'D22',36000,490,48.000,-45.000,52.0,0,NULL),
('AVD007','ORD','LAX',1,'scheduled',NOW()+INTERVAL 1 HOUR,NOW()+INTERVAL 5 HOUR,'H14',NULL,NULL,NULL,NULL,NULL,0,NULL),
('AVD008','DFW','JFK',3,'scheduled',NOW()+INTERVAL 2 HOUR,NOW()+INTERVAL 6 HOUR,'A33',NULL,NULL,NULL,NULL,NULL,0,NULL),
('AVD009','BOS','MIA',11,'scheduled',NOW()+INTERVAL 1 HOUR,NOW()+INTERVAL 4 HOUR,'B07',NULL,NULL,NULL,NULL,NULL,0,NULL),
('AVD010','JFK','LAX',15,'boarding', NOW()+INTERVAL 30 MINUTE,NOW()+INTERVAL 9 HOUR,'B22',NULL,NULL,NULL,NULL,NULL,0,NULL),
('AVD011','LHR','CDG',3,'boarding', NOW()+INTERVAL 20 MINUTE,NOW()+INTERVAL 2 HOUR,'T3-A',NULL,NULL,NULL,NULL,NULL,0,NULL),
('AVD012','LAX','SFO',1,'delayed',  NOW()-INTERVAL 30 MINUTE,NOW()+INTERVAL 2 HOUR,'A05',NULL,NULL,NULL,NULL,NULL,45,'Weather hold'),
('AVD013','ORD','BOS',11,'delayed', NOW()-INTERVAL 1 HOUR,NOW()+INTERVAL 3 HOUR,'H19',NULL,NULL,NULL,NULL,NULL,90,'ATC ground stop'),
('AVD014','JFK','MIA',15,'delayed', NOW()-INTERVAL 2 HOUR,NOW()+INTERVAL 2 HOUR,'B31',NULL,NULL,NULL,NULL,NULL,120,'Crew rest requirement'),
('AVD015','LHR','JFK',9,'landed',   NOW()-INTERVAL 9 HOUR,NOW()-INTERVAL 30 MINUTE,'B14',NULL,NULL,40.639,-73.778,NULL,0,NULL),
('AVD016','NRT','HND',10,'landed',  NOW()-INTERVAL 2 HOUR,NOW()-INTERVAL 1 HOUR,'A04',NULL,NULL,35.549,139.779,NULL,0,NULL),
('AVD017','DFW','ATL',11,'landed',  NOW()-INTERVAL 3 HOUR,NOW()-INTERVAL 1 HOUR,'D15',NULL,NULL,33.636,-84.428,NULL,0,NULL),
('AVD018','SEA','LAX',14,'cancelled',NOW()-INTERVAL 2 HOUR,NULL,'C18',NULL,NULL,NULL,NULL,NULL,0,'Mechanical'),
('AVD019','DEN','ORD',14,'cancelled',NOW()-INTERVAL 1 HOUR,NULL,'C22',NULL,NULL,NULL,NULL,NULL,0,'Winter storm'),
('AVD020','ATL','DFW',15,'departed',NOW()-INTERVAL 30 MINUTE,NOW()+INTERVAL 2 HOUR,'H08',15000,320,32.200,-88.100,92.0,0,NULL),
('AVD021','ORD','DFW',11,'en_route',NOW()-INTERVAL 1 HOUR,NOW()+INTERVAL 2 HOUR,'H22',35000,465,37.500,-91.000,70.0,0,NULL),
('AVD022','JFK','ORD',15,'en_route',NOW()-INTERVAL 1 HOUR,NOW()+INTERVAL 1 HOUR,'B14',36000,470,41.500,-80.000,75.0,0,NULL),
('AVD023','SFO','SEA',13,'en_route',NOW()-INTERVAL 1 HOUR,NOW()+INTERVAL 1 HOUR,'G04',33000,450,44.200,-123.500,80.0,0,NULL),
('AVD024','GRU','JFK',5,'en_route', NOW()-INTERVAL 6 HOUR,NOW()+INTERVAL 4 HOUR,'D09',36000,470,-10.000,-40.000,42.0,0,NULL),
('AVD025','YYZ','LHR',6,'en_route', NOW()-INTERVAL 5 HOUR,NOW()+INTERVAL 2 HOUR,'F14',37000,495,55.000,-28.000,45.0,0,NULL);
