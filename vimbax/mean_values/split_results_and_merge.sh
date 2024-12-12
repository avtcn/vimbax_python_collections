# Split sum of whole photos data
# cp -rf '../output - 副本11.csv' data.csv
cp -rf '../output.txt' data.csv

# Only keep the 2nd column
cut -d ',' -f2 data.csv > data2.csv



# 
rm -rf split_0*
split -l 1000 --numeric-suffixes=1  --suffix-length=5 data2.csv split_ 


# Merge all files in columns mode
paste -d ',' split_0* > merged.csv

# Remove ^M
sed 's/\r//g' merged.csv > merged2.csv



# calulate mean value of each column
result=$( awk -F, '{
    for (i=1; i<=NF; i++) {
        sum[i] += $i;
        count[i]++;
    }
}
END {
    for (i=1; i<=NF; i++) {
        mean[i] = sum[i] / count[i];

    }

    for (i=1; i<=NF; i++) {
        printf "%f", mean[i];
        if (i < NF) {
            printf ", ";
        } else {
            printf "\n";
        }
    }

}' merged2.csv)

echo $result
cp -rf merged2.csv merged3.csv
echo "" >> merged3.csv
echo "" >> merged3.csv
echo $result >> merged3.csv

