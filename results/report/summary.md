# Results summary

Primary AlignAtt variant: **AlignAtt-trim**. Text metrics: computation-unaware runs; latency: computation-unaware LAAL (all indices; primary) and computation-aware LAAL on the virtual clock (CA timing subset of indices; secondary).

## Table 1 (H3)

              index                                                                                                                        0                                                   1
            chunk_s                                                                                                                      0.5                                                 1.0
          WER_LA_en                                                                                                                   10.286                                                6.62
          WER_AA_en                                                                                                                    7.761                                               7.323
       LAALcu_LA_en                                                                                                                    0.675                                               1.598
       LAALcu_AA_en                                                                                                                     0.93                                               1.185
       LAALca_LA_en                                                                                                                      NaN                                               7.404
       LAALca_AA_en                                                                                                                      NaN                                               2.166
               R_en                                                                                                                   24.541                                             -10.616
          WER_LA_id                                                                                                                   15.414                                               8.433
          WER_AA_id                                                                                                                     15.3                                              13.675
       LAALcu_LA_id                                                                                                                    0.773                                               1.873
       LAALcu_AA_id                                                                                                                    1.528                                               1.726
       LAALca_LA_id                                                                                                                      NaN                                               6.943
       LAALca_AA_id                                                                                                                      NaN                                               3.124
               R_id                                                                                                                    0.739                                             -62.162
p_precondition_holm                                                                                                                      0.0                                                0.07
       p_keeps_holm                                                                                                                      0.0                                               0.023
          Delta_pts                                                                                                                  -23.801                                             -51.546
        Delta_ci_lo                                                                                                                  -41.871                                             -82.554
        Delta_ci_hi                                                                                                                   -5.579                                              -21.08
          p_H3_holm                                                                                                                     0.01                                                 0.0
       absDelta_pts                                                                                                                    -2.41                                              -4.539
     absDelta_ci_lo                                                                                                                   -5.011                                              -6.851
     absDelta_ci_hi                                                                                                                    0.121                                              -2.341
  Delta_matched_pts                                                                                                                      NaN                                             -18.455
Delta_matched_ci_lo                                                                                                                      NaN                                             -68.579
Delta_matched_ci_hi                                                                                                                      NaN                                              -4.506
      verdict_fixed                                                                                                                  shrinks not tested (precondition not met; descriptive only)
    verdict_matched not available (the anchor's LAAL is outside the other policy's latency range in at least one language; no extrapolation)                                             shrinks
  equivalence_fixed                                                                                     change larger than +/-0.42 ruled out                a change of +/-0.42 is not ruled out

## H3 (main result)
```
{
 "chunks": {
  "0.5": {
   "R_en": 0.2454077883908891,
   "R_id": 0.0073928043371120165,
   "delta": -0.23801498405377708,
   "ci95_unadjusted": [
    -0.418714230624946,
    -0.05578920137678589
   ],
   "p_boot": 0.01,
   "se": 0.09336479448796589,
   "mde_80": 0.28784366140639883,
   "resamples_dropped": 0,
   "equivalence": {
    "margin": 0.42,
    "smallest_change_excluded": 0.418714230624946,
    "verdict": "change larger than +/-0.42 ruled out"
   },
   "abs_gap_en": 0.025241837968561068,
   "abs_gap_id": 0.0011395578515536187,
   "abs_delta": -0.02410228011700745,
   "abs_delta_ci95": [
    -0.05010901368333735,
    0.0012054355157182894
   ],
   "abs_delta_p_boot": 0.0652,
   "precondition_en": {
    "p": 5.710639561025577e-18,
    "mean_diff": 0.022401619690921984,
    "pooled_diff": 0.025241837968561068
   },
   "keeps_id": {
    "p": 7.084558758235726e-10,
    "mean_diff": 0.012660094676407854,
    "pooled_diff": 0.0011395578515536187
   },
   "wer": {
    "la_en": 0.10285671100362757,
    "aa_en": 0.0776148730350665,
    "la_id": 0.15414419205348326,
    "aa_id": 0.15300463420192964
   },
   "latency": {
    "laal_cu_la_en": 0.6753468603121777,
    "laal_cu_aa_en": 0.9296151002102323,
    "laal_cu_la_id": 0.7732072166858401,
    "laal_cu_aa_id": 1.528448441962489,
    "laal_ca_la_en": null,
    "laal_ca_aa_en": null,
    "laal_ca_la_id": null,
    "laal_ca_aa_id": null
   },
   "precondition_holm": 1.1421279122051155e-17,
   "keeps_holm": 1.4169117516471453e-09,
   "h3_holm": 0.01,
   "precondition_met": true,
   "keeps": true,
   "verdict": "shrinks"
  },
  "1.0": {
   "R_en": -0.10616438356164397,
   "R_id": -0.6216216216216215,
   "delta": -0.5154572380599776,
   "ci95_unadjusted": [
    -0.8255446355992203,
    -0.21080280322794037
   ],
   "p_boot": 0.0002,
   "se": 0.15611501261927418,
   "mde_80": 0.48130258390522235,
   "resamples_dropped": 0,
   "equivalence": {
    "margin": 0.42,
    "smallest_change_excluded": 0.8255446355992203,
    "verdict": "a change of +/-0.42 is not ruled out"
   },
   "abs_gap_en": -0.007028415961305934,
   "abs_gap_id": -0.05241966117146546,
   "abs_delta": -0.045391245210159525,
   "abs_delta_ci95": [
    -0.06851031090136762,
    -0.0234108405961034
   ],
   "abs_delta_p_boot": 0.0,
   "precondition_en": {
    "p": 0.06989721702011249,
    "mean_diff": -0.01344780578449453,
    "pooled_diff": -0.007028415961305934
   },
   "keeps_id": {
    "p": 0.023057221254369868,
    "mean_diff": -0.04418523794681927,
    "pooled_diff": -0.05241966117146546
   },
   "wer": {
    "la_en": 0.06620314389359129,
    "aa_en": 0.07323155985489722,
    "la_id": 0.0843272810149662,
    "aa_id": 0.13674694218643166
   },
   "latency": {
    "laal_cu_la_en": 1.5978076498563685,
    "laal_cu_aa_en": 1.1848208688154438,
    "laal_cu_la_id": 1.8726581959189599,
    "laal_cu_aa_id": 1.7259755578138327,
    "laal_ca_la_en": 7.403835137326621,
    "laal_ca_aa_en": 2.1659869403170187,
    "laal_ca_la_id": 6.94277347084533,
    "laal_ca_aa_id": 3.1242854291535673
   },
   "precondition_holm": 0.06989721702011249,
   "keeps_holm": 0.023057221254369868,
   "h3_holm": 0.0004,
   "precondition_met": false,
   "keeps": false,
   "verdict": "not tested (precondition not met; descriptive only)"
  }
 },
 "metric": "wer",
 "equal_weight": false,
 "la": "la2",
 "aa": "aa_trim"
}
```

## H3 at matched latency (computation-unaware LAAL, primary)
```
{
 "latency_axis": "LAAL, computation-unaware",
 "anchor": "la2",
 "interpolated": "aa_trim",
 "chunks": {
  "0.5": {
   "en": {
    "laal_anchor": 0.6753468603121777,
    "curve_laal_range": [
     0.9296151002102323,
     1.6008253672666286
    ],
    "curve_chunks_used": [
     0.5,
     1.0,
     1.2,
     1.5,
     2.0
    ],
    "wer_la": 0.10285671100362757,
    "wer_aa": null,
    "R": null
   },
   "id": {
    "laal_anchor": 0.7732072166858401,
    "curve_laal_range": [
     1.528448441962489,
     1.954704901908822
    ],
    "curve_chunks_used": [
     0.5,
     1.0,
     1.2,
     1.5,
     2.0
    ],
    "wer_la": 0.15414419205348326,
    "wer_aa": null,
    "R": null
   },
   "verdict": "not available (the anchor's LAAL is outside the other policy's latency range in at least one language; no extrapolation)"
  },
  "1.0": {
   "en": {
    "laal_anchor": 1.5978076498563685,
    "curve_laal_range": [
     0.9296151002102323,
     1.6008253672666286
    ],
    "curve_chunks_used": [
     0.5,
     1.0,
     1.2,
     1.5,
     2.0
    ],
    "wer_la": 0.06620314389359129,
    "wer_aa": 0.06001742396404019,
    "R": 0.09343544076235182
   },
   "id": {
    "laal_anchor": 1.8726581959189599,
    "curve_laal_range": [
     1.528448441962489,
     1.954704901908822
    ],
    "curve_chunks_used": [
     0.5,
     1.0,
     1.2,
     1.5,
     2.0
    ],
    "wer_la": 0.0843272810149662,
    "wer_aa": 0.09201078766888021,
    "R": -0.09111531359051364
   },
   "delta": -0.18455075435286544,
   "ci95_unadjusted": [
    -0.685787168609809,
    -0.04506100010184133
   ],
   "p_boot": 0.0037690594483467533,
   "resamples_outside_range": 4163,
   "equivalence": {
    "margin": 0.42,
    "smallest_change_excluded": 0.685787168609809,
    "verdict": "a change of +/-0.42 is not ruled out"
   },
   "verdict": "shrinks"
  }
 }
}
```

## Offline setup check
```
{
 "en": {
  "wer": 5.805728692485468,
  "ci95": [
   4.9408594129308945,
   6.764437377467885
  ],
  "published": 4.2,
  "pass": false,
  "recordings": 647
 },
 "id": {
  "wer": 7.949291573452648,
  "ci95": [
   6.93389544024252,
   9.02218911185562
  ],
  "published": 7.1,
  "pass": true,
  "recordings": 687
 }
}
```

## WER and latency by run

     policy lang  chunk  recordings     WER    sub    del     ins     CER  splits_per_100w  merges_per_100w  LAAL_cu  LAAL_ca  first_cu  first_ca   RTF  erasure  erasure_raw  tail_conf  spread  share_lagging
    aa_keep   en    0.5         603  43.281  7.716 21.252  14.314  35.949            0.076            0.098    0.896      NaN     1.133       NaN 2.338    0.035        0.120        NaN   3.355            NaN
    aa_keep   en    1.0         603  33.086  6.409 18.954   7.724  28.039            0.045            0.106    1.305    2.194     1.201     2.193 1.410    0.019        0.076        NaN   3.433          1.000
    aa_keep   en    1.2         603  16.226  5.812  1.345   9.069  10.707            0.098            0.144    1.007    2.072     1.411     2.281 1.036    0.019        0.072        NaN   3.221          0.108
    aa_keep   en    1.5         603   9.900  4.021  1.005   4.875   6.271            0.076            0.136    1.115      NaN     1.664       NaN 0.781    0.017        0.061        NaN   3.239            NaN
    aa_keep   en    2.0         603   8.472  3.643  0.801   4.028   5.212            0.091            0.159    1.355      NaN     2.070       NaN 0.688    0.013        0.048        NaN   3.290            NaN
    aa_trim   en    0.5         603   7.761  3.809  1.474   2.479   4.554            0.091            0.166    0.917      NaN     1.819       NaN 2.139    0.077        0.214      0.896   3.019            NaN
    aa_trim   en    1.0         603   7.323  3.461  1.580   2.282   4.411            0.076            0.166    1.173    2.172     2.078     2.964 1.124    0.043        0.131      0.889   3.113          0.932
    aa_trim   en    1.2         603   6.892  3.590  1.187   2.116   3.796            0.098            0.166    1.233    2.406     2.159     3.161 0.980    0.036        0.102      0.888   3.133          0.473
    aa_trim   en    1.5         603   6.091  3.371  0.695   2.025   3.301            0.076            0.159    1.358      NaN     2.236       NaN 0.806    0.027        0.076      0.897   3.152            NaN
    aa_trim   en    2.0         603   6.001  3.174  0.763   2.063   3.215            0.098            0.174    1.597      NaN     2.289       NaN 0.723    0.020        0.058      0.898   3.202            NaN
      hold0   en    0.5         603 145.571 19.143  1.224 125.204 102.935            0.068            0.053   -0.268      NaN     0.619       NaN 4.956    0.000        0.000        NaN     NaN            NaN
      hold0   en    1.0         603  71.660 12.424  1.375  57.860  49.983            0.091            0.076    0.095    3.698     1.073     3.455 2.688    0.000        0.000        NaN     NaN          1.000
      hold0   en    1.2         603  43.523 10.709  1.307  31.507  32.859            0.076            0.083    0.232    3.109     1.300     3.028 2.134    0.000        0.000        NaN     NaN          1.000
      hold0   en    1.5         603  43.984  9.137  1.459  33.389  31.954            0.068            0.091    0.437      NaN     1.555       NaN 1.733    0.000        0.000        NaN     NaN            NaN
      hold0   en    2.0         603  24.463  7.059  1.179  16.226  18.123            0.076            0.128    0.720      NaN     2.013       NaN 1.318    0.000        0.000        NaN     NaN            NaN
hold0_beam5   en    1.0         603  41.022 11.744  1.474  27.804  31.970            0.076            0.091    0.121      NaN     1.017       NaN 3.634    0.000        0.000        NaN     NaN            NaN
      hold2   en    0.5         603 104.353  7.104  0.650  96.599  69.606            0.083            0.098    0.395      NaN     1.638       NaN 4.956    0.347        0.498      0.729     NaN            NaN
      hold2   en    1.0         603  50.257  5.487  0.748  44.022  32.174            0.076            0.106    0.779    4.539     1.922     5.101 2.688    0.192        0.284      0.762     NaN          1.000
      hold2   en    1.2         603  26.141  4.980  0.824  20.337  18.523            0.091            0.121    0.904    3.967     2.030     4.109 2.134    0.158        0.242      0.770     NaN          1.000
      hold2   en    1.5         603  30.736  4.633  0.718  25.385  20.817            0.083            0.121    1.084      NaN     2.162       NaN 1.733    0.116        0.191      0.794     NaN            NaN
      hold2   en    2.0         603  14.941  4.346  0.756   9.840  10.013            0.091            0.144    1.359      NaN     2.322       NaN 1.318    0.086        0.135      0.810     NaN            NaN
hold2_beam5   en    1.0         603  23.972  5.063  0.733  18.176  17.941            0.083            0.113    0.882      NaN     1.756       NaN 3.634    0.167        0.269      0.803     NaN            NaN
        la2   en    0.5         603  10.286  4.580  0.945   4.761   6.722            0.083            0.136    0.673      NaN     1.586       NaN 4.956    1.521        1.698      0.477     NaN            NaN
        la2   en    1.0         603   6.620  3.212  0.748   2.660   3.792            0.083            0.144    1.602    7.307     2.668     6.913 2.688    0.755        0.900      0.645     NaN          1.000
        la2   en    1.2         603   6.462  3.159  0.741   2.562   3.690            0.083            0.144    1.949    6.283     2.979     5.965 2.134    0.415        0.544      0.760     NaN          1.000
        la2   en    1.5         603   6.326  3.076  0.726   2.524   3.586            0.068            0.151    2.485      NaN     3.407       NaN 1.733    0.457        0.570      0.747     NaN            NaN
        la2   en    2.0         603   6.280  3.068  0.680   2.532   3.582            0.091            0.144    3.286      NaN     4.219       NaN 1.318    0.234        0.328      0.852     NaN            NaN
  la2_beam5   en    1.0         603   6.318  3.136  0.680   2.502   3.643            0.076            0.136    1.674      NaN     2.703       NaN 3.634    0.419        0.598      0.772     NaN            NaN
 offline_v2   en    NaN         647   5.806  2.759  0.609   2.437   3.334            0.070            0.161      NaN      NaN       NaN       NaN 0.344      NaN          NaN        NaN     NaN            NaN
 offline_v3   en    NaN         603   5.358  2.811  0.657   1.889   2.946            0.068            0.151      NaN      NaN       NaN       NaN 0.169      NaN          NaN        NaN     NaN            NaN
  ws_anchor   en    1.0         603   6.802  2.993  1.239   2.570   4.320            0.083            0.128    1.733    2.581     2.769     3.408 0.771    0.309        0.507      0.830     NaN          0.217
    aa_keep   id    0.5         680  69.680 18.332 29.849  21.500  55.919            0.144            0.190    1.564      NaN     1.462       NaN 2.389    0.254        0.326        NaN   3.668            NaN
    aa_keep   id    1.0         680  54.874 13.842 35.706   5.326  46.532            0.091            0.220    2.295    4.023     1.640     2.580 1.420    0.144        0.205        NaN   3.814          0.776
    aa_keep   id    1.2         680  33.275 12.490 15.111   5.675  24.215            0.137            0.228    1.924    3.284     2.091     2.944 0.986    0.150        0.210        NaN   3.505          0.165
    aa_keep   id    1.5         680  19.015  8.121  6.549   4.346  12.082            0.175            0.266    1.757      NaN     2.398       NaN 0.942    0.140        0.191        NaN   3.325            NaN
    aa_keep   id    2.0         680  11.981  6.040  1.990   3.950   6.159            0.152            0.258    1.774      NaN     2.459       NaN 0.708    0.106        0.143        NaN   3.248            NaN
    aa_trim   id    0.5         680  15.300  6.503  6.647   2.150   9.627            0.152            0.205    1.540      NaN     2.110       NaN 2.110    0.495        0.635      0.587   3.086            NaN
    aa_trim   id    1.0         680  13.675  6.138  5.546   1.990   8.381            0.137            0.198    1.741    3.192     2.359     3.458 1.194    0.250        0.330      0.594   3.122          0.988
    aa_trim   id    1.2         680   8.927  5.447  1.299   2.180   4.017            0.152            0.220    1.579    2.862     2.546     3.631 1.069    0.191        0.238      0.597   3.063          0.647
    aa_trim   id    1.5         680  10.058  5.759  2.180   2.120   4.918            0.167            0.251    1.776      NaN     2.788       NaN 0.908    0.160        0.199      0.588   3.097            NaN
    aa_trim   id    2.0         680   8.440  5.356  1.003   2.082   3.780            0.160            0.205    1.955      NaN     2.876       NaN 0.720    0.116        0.140      0.603   3.097            NaN
      hold0   id    0.5         680 109.200 32.880  0.593  75.727  89.748            0.008            0.023   -0.157      NaN     0.507       NaN 5.551    0.000        0.000        NaN     NaN            NaN
      hold0   id    1.0         680  66.763 21.955  0.950  43.858  54.340            0.038            0.061    0.174    3.136     1.024     2.757 2.568    0.000        0.000        NaN     NaN          1.000
      hold0   id    1.2         680  50.915 18.674  0.980  31.262  38.979            0.068            0.152    0.354    3.750     1.230     3.322 2.260    0.000        0.000        NaN     NaN          1.000
      hold0   id    1.5         680  47.238 15.278  1.010  30.950  38.014            0.068            0.144    0.581      NaN     1.538       NaN 1.797    0.000        0.000        NaN     NaN            NaN
      hold0   id    2.0         680  32.356 13.143  1.041  18.172  24.845            0.076            0.144    0.899      NaN     2.021       NaN 1.488    0.000        0.000        NaN     NaN            NaN
hold0_beam5   id    1.0         680  38.973 20.421  1.117  17.435  29.134            0.053            0.091    0.279      NaN     1.004       NaN 4.494    0.000        0.000        NaN     NaN            NaN
      hold2   id    0.5         680  59.546  8.934  0.782  49.829  50.749            0.106            0.190    1.026      NaN     1.983       NaN 5.551    0.556        0.687      0.717     NaN            NaN
      hold2   id    1.0         680  38.532  7.286  0.896  30.350  32.026            0.099            0.266    1.348    4.633     2.362     4.694 2.568    0.316        0.397      0.741     NaN          1.000
      hold2   id    1.2         680  28.671  6.906  0.995  20.770  21.593            0.122            0.258    1.487    5.219     2.525     5.308 2.260    0.255        0.327      0.754     NaN          1.000
      hold2   id    1.5         680  30.024  6.450  0.858  22.715  24.692            0.122            0.251    1.650      NaN     2.777       NaN 1.797    0.193        0.252      0.773     NaN            NaN
      hold2   id    2.0         680  20.026  6.100  0.866  13.059  15.358            0.114            0.258    1.928      NaN     2.982       NaN 1.488    0.140        0.187      0.790     NaN            NaN
hold2_beam5   id    1.0         680  14.731  6.123  0.919   7.688   9.609            0.129            0.281    1.529      NaN     2.541       NaN 4.494    0.291        0.387      0.773     NaN            NaN
        la2   id    0.5         680  15.414  7.643  1.132   6.640   9.725            0.122            0.236    0.767      NaN     1.485       NaN 5.551    1.052        1.190      0.540     NaN            NaN
        la2   id    1.0         680   8.433  5.227  0.866   2.340   3.853            0.137            0.273    1.865    6.887     3.110     7.037 2.568    0.691        0.807      0.647     NaN          1.000
        la2   id    1.2         680   7.947  4.999  0.805   2.142   3.476            0.129            0.273    2.241    7.795     3.552     7.939 2.260    0.539        0.659      0.704     NaN          1.000
        la2   id    1.5         680   7.673  4.885  0.760   2.028   3.293            0.137            0.266    2.803      NaN     3.998       NaN 1.797    0.494        0.617      0.726     NaN            NaN
        la2   id    2.0         680   7.627  4.855  0.714   2.059   3.222            0.152            0.289    3.701      NaN     4.791       NaN 1.488    0.343        0.452      0.797     NaN            NaN
  la2_beam5   id    1.0         680   8.030  5.067  0.912   2.051   3.648            0.144            0.289    1.940      NaN     3.238       NaN 4.494    0.433        0.594      0.763     NaN            NaN
 offline_v2   id    NaN         687   7.949  5.429  0.574   1.946   3.236            0.104            0.186      NaN      NaN       NaN       NaN 0.370      NaN          NaN        NaN     NaN            NaN
 offline_v3   id    NaN         680   7.301  4.596  0.638   2.066   3.043            0.160            0.281      NaN      NaN       NaN       NaN 0.167      NaN          NaN        NaN     NaN            NaN
  ws_anchor   id    1.0         680   8.190  5.075  0.912   2.203   3.719            0.114            0.289    1.963    2.980     3.279     3.911 0.922    0.440        0.591      0.760     NaN          0.681
