#pragma once

#include <array>

namespace quic::samples::servermigration {

/**
 * Body size distribution of responses to GET requests.
 */
struct HttpGetResponseBodyDistribution {
  static constexpr std::array<size_t, 800> values{
      500,    1500,   2500,   3500,   4500,   5500,   6500,   7500,   8500,
      9500,   10500,  11500,  12500,  13500,  14500,  15500,  16500,  17500,
      18500,  19500,  20500,  21500,  22500,  23500,  24500,  25500,  26500,
      27500,  28500,  29500,  30500,  31500,  32500,  33500,  34500,  35500,
      36500,  37500,  38500,  39500,  40500,  41500,  42500,  43500,  44500,
      45500,  46500,  47500,  48500,  49500,  50500,  51500,  52500,  53500,
      54500,  55500,  56500,  57500,  58500,  59500,  60500,  61500,  62500,
      63500,  64500,  65500,  66500,  67500,  68500,  69500,  70500,  71500,
      72500,  73500,  74500,  75500,  76500,  77500,  78500,  79500,  80500,
      81500,  82500,  83500,  84500,  85500,  86500,  87500,  88500,  89500,
      90500,  91500,  92500,  93500,  94500,  95500,  96500,  97500,  98500,
      99500,  100500, 101500, 102500, 103500, 104500, 105500, 106500, 107500,
      108500, 109500, 110500, 111500, 112500, 113500, 114500, 115500, 116500,
      117500, 118500, 119500, 120500, 121500, 122500, 123500, 124500, 125500,
      126500, 127500, 128500, 129500, 130500, 131500, 132500, 133500, 134500,
      135500, 136500, 137500, 138500, 139500, 140500, 141500, 142500, 143500,
      144500, 145500, 146500, 147500, 148500, 149500, 150500, 151500, 152500,
      153500, 154500, 155500, 156500, 157500, 158500, 159500, 160500, 161500,
      162500, 163500, 164500, 165500, 166500, 167500, 168500, 169500, 170500,
      171500, 172500, 173500, 174500, 175500, 176500, 177500, 178500, 179500,
      180500, 181500, 182500, 183500, 184500, 185500, 186500, 187500, 188500,
      189500, 190500, 191500, 192500, 193500, 194500, 195500, 196500, 197500,
      198500, 199500, 200500, 201500, 202500, 203500, 204500, 205500, 206500,
      207500, 208500, 209500, 210500, 211500, 212500, 213500, 214500, 215500,
      216500, 217500, 218500, 219500, 220500, 221500, 222500, 223500, 224500,
      225500, 226500, 227500, 228500, 229500, 230500, 231500, 232500, 233500,
      234500, 235500, 236500, 237500, 238500, 239500, 240500, 241500, 242500,
      243500, 244500, 245500, 246500, 247500, 248500, 249500, 250500, 251500,
      252500, 253500, 254500, 255500, 256500, 257500, 258500, 259500, 260500,
      261500, 262500, 263500, 264500, 265500, 266500, 267500, 268500, 269500,
      270500, 271500, 272500, 273500, 274500, 275500, 276500, 277500, 278500,
      279500, 280500, 281500, 282500, 283500, 284500, 285500, 286500, 287500,
      288500, 289500, 290500, 291500, 292500, 293500, 294500, 295500, 296500,
      297500, 298500, 299500, 300500, 301500, 302500, 303500, 304500, 305500,
      306500, 307500, 308500, 309500, 310500, 311500, 312500, 313500, 314500,
      315500, 316500, 317500, 318500, 319500, 320500, 321500, 322500, 323500,
      324500, 325500, 326500, 327500, 328500, 329500, 330500, 331500, 332500,
      333500, 334500, 335500, 336500, 337500, 338500, 339500, 340500, 341500,
      342500, 343500, 344500, 345500, 346500, 347500, 348500, 349500, 350500,
      351500, 352500, 353500, 354500, 355500, 356500, 357500, 358500, 359500,
      360500, 361500, 362500, 363500, 364500, 365500, 366500, 367500, 368500,
      369500, 370500, 371500, 372500, 373500, 374500, 375500, 376500, 377500,
      378500, 379500, 380500, 381500, 382500, 383500, 384500, 385500, 386500,
      387500, 388500, 389500, 390500, 391500, 392500, 393500, 394500, 395500,
      396500, 397500, 398500, 399500, 400500, 401500, 402500, 403500, 404500,
      405500, 406500, 407500, 408500, 409500, 410500, 411500, 412500, 413500,
      414500, 415500, 416500, 417500, 418500, 419500, 420500, 421500, 422500,
      423500, 424500, 425500, 426500, 427500, 428500, 429500, 430500, 431500,
      432500, 433500, 434500, 435500, 436500, 437500, 438500, 439500, 440500,
      441500, 442500, 443500, 444500, 445500, 446500, 447500, 448500, 449500,
      450500, 451500, 452500, 453500, 454500, 455500, 456500, 457500, 458500,
      459500, 460500, 461500, 462500, 463500, 464500, 465500, 466500, 467500,
      468500, 469500, 470500, 471500, 472500, 473500, 474500, 475500, 476500,
      477500, 478500, 479500, 480500, 481500, 482500, 483500, 484500, 485500,
      486500, 487500, 488500, 489500, 490500, 491500, 492500, 493500, 494500,
      495500, 496500, 497500, 498500, 499500, 500500, 501500, 502500, 503500,
      504500, 505500, 506500, 507500, 508500, 509500, 510500, 511500, 512500,
      513500, 514500, 515500, 516500, 517500, 518500, 519500, 520500, 521500,
      522500, 523500, 524500, 525500, 526500, 527500, 528500, 529500, 530500,
      531500, 532500, 533500, 534500, 535500, 536500, 537500, 538500, 539500,
      540500, 541500, 542500, 543500, 544500, 545500, 546500, 547500, 548500,
      549500, 550500, 551500, 552500, 553500, 554500, 555500, 556500, 557500,
      558500, 559500, 560500, 561500, 562500, 563500, 564500, 565500, 566500,
      567500, 568500, 569500, 570500, 571500, 572500, 573500, 574500, 575500,
      576500, 577500, 578500, 579500, 580500, 581500, 582500, 583500, 584500,
      585500, 586500, 587500, 588500, 589500, 590500, 591500, 592500, 593500,
      594500, 595500, 596500, 597500, 598500, 599500, 600500, 601500, 602500,
      603500, 604500, 605500, 606500, 607500, 608500, 609500, 610500, 611500,
      612500, 613500, 614500, 615500, 616500, 617500, 618500, 619500, 620500,
      621500, 622500, 623500, 624500, 625500, 626500, 627500, 628500, 629500,
      630500, 631500, 632500, 633500, 634500, 635500, 636500, 637500, 638500,
      639500, 640500, 641500, 642500, 643500, 644500, 645500, 646500, 647500,
      648500, 649500, 650500, 651500, 652500, 653500, 654500, 655500, 656500,
      657500, 658500, 659500, 660500, 661500, 662500, 663500, 664500, 665500,
      666500, 667500, 668500, 669500, 670500, 671500, 672500, 673500, 674500,
      675500, 676500, 677500, 678500, 679500, 680500, 681500, 682500, 683500,
      684500, 685500, 686500, 687500, 688500, 689500, 690500, 691500, 692500,
      693500, 694500, 695500, 696500, 697500, 698500, 699500, 700500, 701500,
      702500, 703500, 704500, 705500, 706500, 707500, 708500, 709500, 710500,
      711500, 712500, 713500, 714500, 715500, 716500, 717500, 718500, 719500,
      720500, 721500, 722500, 723500, 724500, 725500, 726500, 727500, 728500,
      729500, 730500, 731500, 732500, 733500, 734500, 735500, 736500, 737500,
      738500, 739500, 740500, 741500, 742500, 743500, 744500, 745500, 746500,
      747500, 748500, 749500, 750500, 751500, 752500, 753500, 754500, 755500,
      756500, 757500, 758500, 759500, 760500, 761500, 762500, 763500, 764500,
      765500, 766500, 767500, 768500, 769500, 770500, 771500, 772500, 773500,
      774500, 775500, 776500, 777500, 778500, 779500, 780500, 781500, 782500,
      783500, 784500, 785500, 786500, 787500, 788500, 789500, 790500, 791500,
      792500, 793500, 794500, 795500, 796500, 797500, 798500, 799500};

  static constexpr std::array<double, 800> probabilities{
      0.6994313294093885,     0.044120238978233355,   0.018887049388040016,
      0.01681654847178522,    0.019568470729841244,   0.02976440983758863,
      0.042182840849085995,   0.017184042020579403,   0.01249826317094872,
      0.01162388705706137,    0.012710460297179862,   0.00313836303286417,
      0.0018258101827941008,  0.0013749724497889658,  0.0014963291372802668,
      0.0010404447132340293,  0.001211855131752871,   0.002006015419618489,
      0.0011046055689261716,  0.000916815539133577,   0.0012841910366753367,
      0.001696485035764217,   0.0011223722824159,     0.0011702715780867127,
      0.0013232660012274969,  0.0009630326044573555,  0.0013705455278230866,
      0.000978054626328239,   0.0015722065797754358,  0.0018675413005257884,
      0.001558158480737046,   0.0013456367135617397,  0.0012913036246338494,
      0.0008147897442266149,  0.0007217948701300465,  0.0009107654124468755,
      0.0006523512208919551,  0.0003529142191198878,  0.0003043361287476403,
      0.00038682444137852224, 0.00036182708867785787, 0.0003921367477375773,
      0.00039346482432734103, 0.00044859475920908966, 0.0006054848736798476,
      0.0004336907885906298,  0.00031327851111871626, 0.00031478366458711517,
      0.00046526949861390123, 0.0002742625721927678,  0.00036917577914121727,
      0.0003426142473459422,  0.00033042545553322157, 0.0002243268924176507,
      0.00028482815928466607, 0.0002504457320163378,  0.0002473468866402224,
      0.00020611748673133435, 0.00033653460784613485, 0.00021358422844711724,
      0.00018737685040911252, 0.00015305344876699598, 0.0002001558984839504,
      0.00021860140667511363, 0.00020254643634552515, 0.00024776006602370443,
      0.0001624680361477657,  0.00016896085503105516, 0.000261896703501412,
      0.00018542900474412567, 0.0001487150652404344,  0.00017324021293140503,
      0.00022845868625247126, 0.000111174766969779,   0.00010069771831719829,
      0.00015703767853628725, 0.0001275248654304261,  0.0001555620378809942,
      0.0001230979434645469,  0.00015815916543430997, 0.00013806093970921852,
      9.576907852851947e-05,  0.00011241430512022517, 9.497223257466122e-05,
      0.00010435730714232507, 0.00014481937391046072, 0.0001200581237146432,
      0.00014738698865067064, 0.00010733810126601705, 0.00010105187207446862,
      0.00011288651012991894, 0.00010400315338505474, 0.00010674784500389982,
      0.00016792790657235002, 0.00010043210299924553, 8.325564577163434e-05,
      7.983215945135444e-05,  7.271957149284191e-05,  8.360979952890468e-05,
      8.47312864269274e-05,   8.915820839280657e-05,  9.275877159172164e-05,
      8.358028671579882e-05,  8.983700309424138e-05,  9.45295403780733e-05,
      7.555280155100458e-05,  8.614790145600873e-05,  7.118490521133712e-05,
      6.64923679275052e-05,   7.670380126213315e-05,  7.528718623305182e-05,
      0.00013620163248354925, 7.077172582785507e-05,  8.239977419156437e-05,
      7.608403218691008e-05,  7.425423777434668e-05,  0.00011031889538970903,
      7.333934056806498e-05,  9.503125820087295e-05,  8.626595270843218e-05,
      8.620692708222045e-05,  0.00011445068922452958, 0.007560799051151253,
      8.759402929819592e-05,  6.740726513378689e-05,  7.513962216752251e-05,
      7.546426311168699e-05,  6.77909317041631e-05,   6.720067544204586e-05,
      8.561667082010323e-05,  7.52281606068401e-05,   8.254733825709368e-05,
      7.912385193681377e-05,  8.836136243894832e-05,  8.76235421113018e-05,
      8.074705665763613e-05,  8.408200453859845e-05,  7.909433912370791e-05,
      0.00011660512458125745, 7.431326340055841e-05,  6.250813815821395e-05,
      6.286229191548428e-05,  5.7992677753017184e-05, 6.247862534510807e-05,
      6.159324095193224e-05,  6.365913786934252e-05,  6.336400973828391e-05,
      7.513962216752251e-05,  8.301954326678744e-05,  7.782528816015589e-05,
      7.02109823788437e-05,   6.424939413145976e-05,  6.339352255138978e-05,
      0.0001012879745793155,  9.571005290230775e-05,  7.717600627182694e-05,
      6.100298468981502e-05,  7.419521214813496e-05,  7.835651879606139e-05,
      6.289180472859014e-05,  6.20064203354143e-05,   6.0265164362168495e-05,
      4.902078256883539e-05,  5.4893832376901764e-05, 5.309355077744423e-05,
      6.303936879411945e-05,  5.256232014153873e-05,  5.778608806127616e-05,
      6.640382948818762e-05,  5.0998141046928086e-05, 5.6517037097724125e-05,
      5.890757495929888e-05,  5.4893832376901764e-05, 5.386088391819662e-05,
      5.964539528694541e-05,  5.52479861341721e-05,   0.00023704691486627685,
      4.491850154712069e-05,  4.7781244418389224e-05, 5.026032071928156e-05,
      9.284731003103921e-05,  6.566600916054109e-05,  4.881419287709436e-05,
      5.498237081621935e-05,  7.82679803567438e-05,   5.102765386003395e-05,
      6.115054875534433e-05,  7.652672438349799e-05,  7.770723690773244e-05,
      8.691523459676112e-05,  8.614790145600873e-05,  9.571005290230775e-05,
      0.00010736761407912291, 7.69103909538742e-05,   7.236541773557157e-05,
      0.00011418507390657684, 6.005857467042746e-05,  7.00634183133144e-05,
      5.693021648120618e-05,  0.00014390447670417902, 0.00012147473874372454,
      6.867631609733893e-05,  4.77222187921775e-05,   4.902078256883539e-05,
      6.70235985634107e-05,   5.294598671191492e-05,  4.896175694262367e-05,
      4.801734692323611e-05,  4.379701464909796e-05,  4.0521092394347375e-05,
      4.385604027530969e-05,  4.2262348367593185e-05, 3.886837486041915e-05,
      3.7304195765808506e-05, 4.205575867585216e-05,  3.7717375149290564e-05,
      3.7687862336184705e-05, 3.928155424390121e-05,  3.653686262505612e-05,
      4.6836834399001665e-05, 3.89864261128426e-05,   3.638929855952681e-05,
      4.851906474603575e-05,  3.281824817371761e-05,  3.910447736526604e-05,
      3.5444888540139253e-05, 3.520878603529237e-05,  3.2995325052352776e-05,
      3.402827351105792e-05,  3.3910222258634476e-05, 3.751078545754954e-05,
      3.1637735649483166e-05, 3.270019692129417e-05,  3.7009067634749896e-05,
      3.225750472470625e-05,  3.213945347228281e-05,  3.4884145091127894e-05,
      3.444145289453998e-05,  0.00018522241505238466, 3.6359785746420954e-05,
      3.529732447460995e-05,  3.5385862913927536e-05, 2.7564967440874324e-05,
      3.1372120331530415e-05, 3.172627408880075e-05,  2.9070120909273246e-05,
      2.8509377460261883e-05, 2.9247197787908413e-05, 2.847986464715602e-05,
      3.208042784607108e-05,  2.8302787768520854e-05, 2.7771557132615353e-05,
      2.594176272005196e-05,  2.6856659926333657e-05, 2.974891561070805e-05,
      2.688617273943952e-05,  4.503655279954413e-05,  2.5764685841416793e-05,
      2.4584173317182346e-05, 2.8627428712685326e-05, 2.6974711178757103e-05,
      2.800765963746224e-05,  2.561712177588749e-05,  2.361025048468893e-05,
      2.7063249618074686e-05, 2.762399306708605e-05,  2.8273274955414992e-05,
      2.5705660215205072e-05, 3.733370857891437e-05,  2.561712177588749e-05,
      3.0575274377672165e-05, 2.5499070523464043e-05, 2.889304403063808e-05,
      2.6650070234592628e-05, 2.390537861574754e-05,  2.667958304769849e-05,
      2.411196830748857e-05,  2.4554660504076488e-05, 2.414148112059443e-05,
      2.4259532373017875e-05, 3.2050915032965224e-05, 3.116553063978939e-05,
      2.6443480542851602e-05, 2.5469557710358184e-05, 2.7564967440874324e-05,
      2.361025048468893e-05,  2.2695353278407232e-05, 2.5823711467628518e-05,
      2.8361813394732575e-05, 2.260681483908965e-05,  2.2488763586666206e-05,
      2.2783891717724815e-05, 2.6000788346263685e-05, 2.1249225436220038e-05,
      2.673860867391021e-05,  2.2193635455607594e-05, 2.2960968596359986e-05,
      2.0747507613420396e-05, 2.1957532950760706e-05, 2.257730202598379e-05,
      2.5587608962781626e-05, 2.5203942392405434e-05, 2.4466122064758904e-05,
      2.1603379193490372e-05, 2.2724866091513094e-05, 2.290194297014826e-05,
      2.2724866091513094e-05, 2.107214855758487e-05,  2.331512235363032e-05,
      2.110166137069073e-05,  2.4466122064758904e-05, 3.0427710312142857e-05,
      2.1278738249325897e-05, 2.110166137069073e-05,  2.6502506169063323e-05,
      2.7269839309815715e-05, 2.3698788924006512e-05, 2.514491676619371e-05,
      2.316755828810101e-05,  2.517442957929957e-05,  2.6089326785581268e-05,
      2.133776387553762e-05,  2.0924584492055563e-05, 2.3226583914312736e-05,
      2.514491676619371e-05,  2.5735173028310934e-05, 8.399346609928087e-05,
      1.8858687574645282e-05, 2.1190199810008314e-05, 2.3079019848783428e-05,
      2.7240326496709853e-05, 2.1868994511443122e-05, 0.0007515437857407545,
      2.5203942392405434e-05, 2.4289045186123737e-05, 2.183948169833726e-05,
      2.741740337534502e-05,  2.062945636099695e-05,  2.2341199521136898e-05,
      2.2695353278407232e-05, 2.411196830748857e-05,  6.507575289842386e-05,
      2.514491676619371e-05,  2.2341199521136898e-05, 2.1485327941066926e-05,
      2.3728301737112374e-05, 2.1249225436220038e-05, 2.1957532950760706e-05,
      2.4200506746806154e-05, 3.025063343350769e-05,  2.2341199521136898e-05,
      2.6856659926333657e-05, 2.5587608962781626e-05, 2.9866966863131497e-05,
      2.4702224569605792e-05, 2.4967839887558542e-05, 2.3285609540524457e-05,
      2.5262968018617155e-05, 2.1957532950760706e-05, 2.331512235363032e-05,
      2.151484075417279e-05,  2.4997352700664405e-05, 3.078186406941319e-05,
      2.03638410430442e-05,   2.183948169833726e-05,  2.0747507613420396e-05,
      2.6059813972475406e-05, 2.4230019559912013e-05, 2.3197071101206874e-05,
      2.210509701629001e-05,  2.2282173894925177e-05, 2.0658969174102813e-05,
      2.136727668864348e-05,  2.8597915899579467e-05, 2.231168670803104e-05,
      2.0983610118267288e-05, 2.363976329779479e-05,  6.233106127957878e-05,
      2.110166137069073e-05,  2.694519836565124e-05,  2.845035183405016e-05,
      2.2990481409465845e-05, 2.1987045763866564e-05, 2.384635298953582e-05,
      2.1809968885231398e-05, 2.567614740209921e-05,  2.59122499069461e-05,
      2.178045607212554e-05,  2.130825106243176e-05,  1.9685046341609395e-05,
      2.464319894339407e-05,  2.0983610118267288e-05, 8.242928700467023e-05,
      2.178045607212554e-05,  1.98326104071387e-05,   1.856355944358667e-05,
      2.077702042652626e-05,  2.1219712623114176e-05, 2.0599943547891092e-05,
      2.0275302603726617e-05, 1.980309759403284e-05,  2.062945636099695e-05,
      1.726499566692878e-05,  2.1928020137654843e-05, 2.0216276977514896e-05,
      2.2488763586666206e-05, 1.8445508191163227e-05, 1.673376503102328e-05,
      1.8150380060104614e-05, 1.826843131252806e-05,  1.980309759403284e-05,
      2.110166137069073e-05,  2.845035183405016e-05,  1.7501098171775668e-05,
      1.826843131252806e-05,  1.8947226013962865e-05, 1.9626020715397674e-05,
      2.0895071678949704e-05, 2.2872430157042402e-05, 1.8150380060104614e-05,
      1.7648662237304976e-05, 1.9094790079492173e-05, 1.7973303181469448e-05,
      1.800281599457531e-05,  1.8386482564951503e-05, 2.3433173606053762e-05,
      2.03638410430442e-05,   1.779622630283428e-05,  1.5140073123306776e-05,
      1.8356969751845644e-05, 1.5907406264059166e-05, 1.803232880768117e-05,
      1.977358478092698e-05,  1.9094790079492173e-05, 1.826843131252806e-05,
      1.8711123509115977e-05, 1.9183328518809757e-05, 1.6851816283446722e-05,
      1.5848380637847445e-05, 1.5730329385424e-05,    2.0275302603726617e-05,
      1.5317150001941945e-05, 1.7619149424199114e-05, 1.7146944414505334e-05,
      1.9153815705703895e-05, 1.620253439511778e-05,  1.6910841909658446e-05,
      1.903576445328045e-05,  1.6143508768906054e-05, 1.7117431601399476e-05,
      1.552373969368297e-05,  1.6143508768906054e-05, 1.5022021870883332e-05,
      1.5966431890270887e-05, 1.4579329674295415e-05, 1.5022021870883332e-05,
      1.5287637188836082e-05, 1.8976738827068728e-05, 1.4962996244671609e-05,
      1.3192227458319939e-05, 1.522861156262436e-05,  1.4608842487401275e-05,
      1.552373969368297e-05,  1.4903970618459886e-05, 1.8415995378057365e-05,
      1.4638355300507136e-05, 1.7825739115940143e-05, 1.3841509346648885e-05,
      1.4018586225284052e-05, 1.5435201254365387e-05, 1.4756406552930582e-05,
      1.605497032958847e-05,  1.3516868402484412e-05, 1.5907406264059166e-05,
      1.5405688441259528e-05, 1.694035472276431e-05,  1.2572458383096855e-05,
      1.3221740271425801e-05, 1.1893663681662048e-05, 1.4520304048083692e-05,
      1.3959560599072329e-05, 1.758963661109325e-05,  1.5199098749518499e-05,
      1.4372739982554386e-05, 1.3310278710743384e-05, 1.3959560599072329e-05,
      1.4166150290813358e-05, 1.3369304336955106e-05, 1.2808560887943744e-05,
      1.7353534106246364e-05, 1.242489431756755e-05,  1.2631484009308578e-05,
      1.3192227458319939e-05, 1.1273894606438964e-05, 1.5966431890270887e-05,
      1.6291072834435362e-05, 1.4549816861189553e-05, 1.4815432179142303e-05,
      1.065412553121588e-05,  1.3841509346648885e-05, 1.1893663681662048e-05,
      1.3752970907331302e-05, 1.0270458960839684e-05, 1.1391945858862408e-05,
      1.2867586514155467e-05, 1.0536074278792436e-05, 1.0860715222956907e-05,
      1.2100253373403077e-05, 1.4697380926718859e-05, 1.1775612429238604e-05,
      1.1746099616132743e-05, 1.0358997400157267e-05, 1.0211433334627962e-05,
      9.680202698722462e-06,  1.0624612718110019e-05, 1.2808560887943744e-05,
      0.0006249338175166101,  1.1391945858862408e-05, 1.2159278999614798e-05,
      1.1834638055450327e-05, 1.2395381504461688e-05, 1.4107124664601635e-05,
      1.2011714934085493e-05, 1.1244381793333103e-05, 1.0565587091898296e-05,
      1.0299971773945546e-05, 9.709715511828322e-06,  1.089022803606277e-05,
      9.119459249711099e-06,  1.0034356455992796e-05, 1.0536074278792436e-05,
      1.7412559732458085e-05, 1.1303407419544824e-05, 1.065412553121588e-05,
      1.0034356455992796e-05, 1.0772176783639324e-05, 3.9694733627383265e-05,
      4.5626809061661355e-05, 8.735792679334905e-06,  9.119459249711099e-06,
      8.942382371075932e-06,  1.1480484298179993e-05, 1.0240946147733823e-05,
      9.798253951145906e-06,  9.91630520356935e-06,   6.817459827453929e-06,
      1.1775612429238604e-05, 9.030920810393516e-06,  7.909433912370791e-06,
      8.617741426911459e-06,  8.794818305546626e-06,  1.089022803606277e-05,
      8.293100482746986e-06,  9.532638633193156e-06,  8.175049230323542e-06,
      7.024049519194956e-06,  9.178484875922822e-06,  1.065412553121588e-05,
      1.0831202409851047e-05, 8.263587669641125e-06,  6.787947014348067e-06,
      7.053562332300818e-06,  7.968459538582514e-06,  7.289664837147707e-06,
      9.326048941452126e-06,  0.0007024344647326015,  9.237510502134543e-06,
      6.138665126019122e-06,  8.942382371075932e-06,  7.289664837147707e-06,
      7.1716135847242625e-06, 9.591664259404878e-06,  1.3428329963166828e-05,
      8.175049230323542e-06,  8.529202987593875e-06,  6.846972640559789e-06,
      7.053562332300818e-06,  8.971895184181793e-06,  6.6698957619246225e-06,
      7.732357033735625e-06,  1.0093382082204517e-05, 6.551844509501178e-06,
      6.079639499807399e-06,  6.817459827453929e-06,  6.374767630866011e-06,
      5.489383237690176e-06,  9.798253951145906e-06,  9.680202698722462e-06,
      7.466741715782874e-06,  1.0270458960839684e-05, 8.942382371075932e-06,
      1.1126330540909657e-05, 8.263587669641125e-06,  6.227203565336705e-06,
      5.695972929431204e-06,  6.286229191548427e-06,  5.784511368748788e-06,
      6.935511079877373e-06,  5.84353699496051e-06,   8.588228613805598e-06,
      6.1091523129132605e-06, 7.820895473053208e-06,  5.253280732843287e-06,
      8.027485164794235e-06,  6.581357322607039e-06,  6.758434201242206e-06,
      8.588228613805598e-06,  5.84353699496051e-06,   5.636947303219482e-06,
      6.315742004654289e-06,  6.728921388136345e-06,  4.456434778985036e-06,
      7.850408286159069e-06,  5.84353699496051e-06,   4.899126975572953e-06,
      5.57792167700776e-06,   4.8105885362553695e-06, 6.286229191548427e-06,
      6.6698957619246225e-06, 5.548408863901898e-06,  7.1716135847242625e-06,
      4.102281021714701e-06,  6.581357322607039e-06,  9.089946436605238e-06,
      4.485947592090896e-06,  7.083075145406679e-06,  4.928639788678814e-06,
      6.286229191548427e-06,  7.348690463359429e-06,  6.256716378442567e-06,
      4.7515629100436475e-06, 5.105716667313981e-06,  4.544973218302619e-06,
      6.994536706089096e-06,  5.3713319852667315e-06, 7.053562332300818e-06,
      4.57448603140848e-06,   4.663024470726063e-06,  5.814024181854649e-06,
      5.991101060489816e-06,  1.4195663103919219e-05, 1.2749535261732022e-05,
      1.1982202120979631e-05, 5.046691041102258e-06,  3.777640077550229e-06,
      5.518896050796037e-06,  4.987665414890536e-06,  6.433793257077734e-06,
      5.253280732843287e-06,  4.8696141624670915e-06, 6.492818883289456e-06,
      7.643818594418041e-06,  7.11258795851254e-06,   5.8730498080663716e-06,
      5.046691041102258e-06,  5.84353699496051e-06,   8.499690174488015e-06,
      4.840101349361231e-06,  5.636947303219482e-06,  9.709715511828322e-06,
      1.2542945569990994e-05, 9.089946436605238e-06,  1.2247817438932381e-05,
      1.6615713778599834e-05, 9.444100193875572e-06,  1.2720022448626161e-05,
      5.4303576114784535e-06, 6.138665126019122e-06,  7.791382659947347e-06,
      4.899126975572953e-06,  6.315742004654289e-06,  5.400844798372593e-06,
      5.400844798372593e-06,  5.489383237690176e-06,  6.905998266771512e-06,
      3.895691329973674e-06,  5.3713319852667315e-06, 5.548408863901898e-06,
      5.518896050796037e-06,  7.496254528888735e-06,  4.3088707134557295e-06,
      4.485947592090896e-06,  4.57448603140848e-06,   3.954716956185396e-06,
      4.397409152773313e-06,  1.0506561465686573e-05, 7.61430578131218e-06,
      9.739228324934183e-06,  3.275922254750589e-06,  5.017178227996398e-06,
      3.452999133385756e-06,  3.6891016382326454e-06, 5.57792167700776e-06,
      3.895691329973674e-06,  4.131793834820563e-06,  3.866178516867812e-06,
      4.485947592090896e-06,  5.695972929431204e-06,  9.473613006981433e-06,
      4.161306647926424e-06,  6.34525481776015e-06,   3.954716956185396e-06,
      3.7481272644443674e-06, 4.722050096937786e-06,  2.9807941236919775e-06,
      3.5415375727033395e-06, 3.1283581892212834e-06, 3.0398197499036995e-06,
      4.57448603140848e-06,   3.452999133385756e-06,  3.216896628538867e-06,
      2.4200506746806155e-06, 4.692537283831925e-06,  6.640382948818761e-06,
      4.279357900349869e-06,  4.2498450872440075e-06, 3.954716956185396e-06,
      3.600563198915062e-06,  3.5415375727033395e-06, 3.3349478809623112e-06,
      3.954716956185396e-06,  3.246409441644728e-06,  3.984229769291257e-06,
      3.1283581892212834e-06, 3.5710503858092005e-06, 7.053562332300818e-06,
      4.899126975572953e-06,  3.895691329973674e-06,  3.866178516867812e-06,
      3.275922254750589e-06,  4.338383526561591e-06,  3.482511946491617e-06,
      6.492818883289456e-06,  3.3349478809623112e-06, 8.470177361382154e-06,
      3.866178516867812e-06,  3.954716956185396e-06,  5.548408863901898e-06,
      2.7151788057392268e-06, 3.0103069367978385e-06, 2.5971275533157823e-06,
      3.275922254750589e-06,  3.3644606940681727e-06, 5.902562621172232e-06,
      6.227203565336705e-06,  5.017178227996398e-06,  3.659588825126784e-06,
      2.567614740209921e-06,  3.5415375727033395e-06, 3.246409441644728e-06,
      5.223767919737426e-06,  4.043255395502979e-06,  3.866178516867812e-06,
      3.5415375727033395e-06, 5.282793545949148e-06,  3.984229769291257e-06,
      6.551844509501178e-06,  4.485947592090896e-06,  5.253280732843287e-06,
      4.3088707134557295e-06, 4.899126975572953e-06,  5.991101060489816e-06,
      4.043255395502979e-06,  6.286229191548427e-06,  3.659588825126784e-06,
      4.102281021714701e-06,  4.220332274138146e-06,  3.954716956185396e-06,
      3.954716956185396e-06,  3.5710503858092005e-06, 4.279357900349869e-06,
      4.131793834820563e-06,  6.197690752230844e-06,  4.013742582397118e-06,
      5.194255106631565e-06,  9.178484875922822e-06,  7.702844220629764e-06,
      5.07620385420812e-06,   4.072768208608841e-06,  6.6108701357129005e-06,
      4.367896339667452e-06,  4.603998844514341e-06,  4.3088707134557295e-06,
      4.043255395502979e-06,  4.367896339667452e-06,  6.256716378442567e-06,
      5.57792167700776e-06,   4.072768208608841e-06,  5.754998555642927e-06,
      4.279357900349869e-06,  7.378203276465291e-06,  3.246409441644728e-06,
      3.836665703761951e-06,  4.161306647926424e-06,  3.7186144513385064e-06,
      3.80715289065609e-06,   5.07620385420812e-06,   3.7481272644443674e-06,
      4.279357900349869e-06,  3.80715289065609e-06};
};

} // namespace quic::samples::servermigration